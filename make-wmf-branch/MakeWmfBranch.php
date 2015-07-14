<?php

class MakeWmfBranch {
	var $dryRun;
	var $newVersion, $oldVersion, $buildDir;
	var $specialExtensions, $branchedExtensions, $branchedSkins, $patches;
	var $baseRepoPath, $anonRepoPath;
	var $noisy;
	var $cli;
	var $state;
	var $cmdLog = array();
	var $logOnly = false;
	function __construct( $cli ) {
		$this->cli = $cli;
		$this->newVersion = $cli->arguments->get('branch');
		$this->oldVersion = $cli->arguments->get('base');

		$buildDir = sys_get_temp_dir() . '/make-wmf-branch';

		require __DIR__ . '/default.conf';

		$branchLists = json_decode(
			file_get_contents( __DIR__ . '/config.json' ),
			true
		);

		// if we are resuming then load the state from last run
		if ($cli->arguments->defined('resume')
			&& file_exists('/tmp/make-wmf-branch.state')) {
			$lastRunState = json_decode(
				file_get_contents( '/tmp/make-wmf-branch.state'),
				true
			);
		} else {
			$lastRunState = null;
		}

		// This comes after we load all the default configuration
		// so it is possible to override default.conf and $branchLists
		if ( file_exists( __DIR__ . '/local.conf' ) ) {
			require __DIR__ . '/local.conf';
		}

		$this->loadState($branchLists, $lastRunState);
		$this->dryRun = $dryRun || $cli->arguments->defined('dryRun');
		$this->buildDir = $buildDir;
		$this->noisy = $noisy || $cli->arguments->defined('verbose');
		$this->patches = $patches;
		$this->baseRepoPath = $baseRepoPath;
		$this->anonRepoPath = $anonRepoPath;
		$this->branchPrefix = $branchPrefix;
		$this->logOnly = $cli->arguments->defined('logOnly');
	}

	function loadState($branchLists, $lastRunState=null) {
		foreach(['extensions','skins'] as $name) {
			$list = $branchLists[$name];
			$newlist = [];
			foreach($list as $extension) {
				if (isset($lastRunState[$name][$extension])) {
					$newlist[$extension] = $lastRunState[$name][$extension];
				} else {
					$newlist[$extension] = null;
				}
			}
			$branchLists[$name] = $newlist;
		}

		$this->branchedExtensions = $branchLists['extensions'];
		$this->branchedSubmodules = $branchLists['submodules'];
		$this->branchedSkins = $branchLists['skins'];
		$this->specialExtensions = $branchLists['special_extensions'];
	}

	function abortSavingState() {
		$result = $this->saveState();
		if ($result === false) {
			$this->cli->out('Unable to save state to file. Dumping state instead:');
			$this->cli->out($this->state);
		}
		exit(1);
	}

	function saveState() {
		$state = [
			'extensions' => $this->branchedExtensions,
			'skins' => $this->branchedSkins,
		];
		$this->state = serialize($state);
		return file_put_contents('/tmp/mae-wmf-branch.state', $this->state);
	}

	function runCmd( /*...*/ ) {
		$args = func_get_args();
		if( $this->noisy && in_array( "-q", $args ) ) {
			$args = array_diff( $args, array( "-q" ) );
		}
		$encArgs = array_map( 'escapeshellarg', $args );
		$cmd = implode( ' ', $encArgs );
		$this->cmdLog[] = $cmd;
		if ($this->logOnly){
			return;
		}
		$attempts = 0;
		do {
			echo "$cmd\n";
			if ($this->dryRun) {
				return;
			}
			passthru( $cmd, $ret );

			if ( !$ret ) {
				// It worked!
				return;
			}
			echo "sleeping for 5s\n";
			sleep( 5 );
		} while ( ++$attempts <= 5 );
		$this->croak( $args[0] . " exit with status $ret\n" );
	}

	function runWriteCmd( /*...*/ ) {
		$args = func_get_args();
		if ( $this->dryRun ) {
			$encArgs = array_map( 'escapeshellarg', $args );
			$cmd = implode( ' ', $encArgs );
			echo "$cmd\n";
		} else {
			call_user_func_array( array( $this, 'runCmd' ), $args );
		}
	}

	function chdir( $dir ) {
		if ( !chdir( $dir ) ) {
			$this->croak( "Unable to change working directory\n" );
		}
		echo "cd $dir\n";
	}

	function croak( $msg ) {
		$this->cli->to('error')->red("$msg")->br();
		throw new Exception($msg);
	}

	function execute() {
		if ($this->cli->arguments->defined('localClone')) {
			$clonePath = $this->cli->arguments->get('localClone');
		} else {
			$clonePath = null;
		}
		$this->setupBuildDirectory();
		foreach( $this->branchedExtensions as $ext => $status) {
			if ($status === null) {
				try {
					$status = $this->branchRepo( "extensions/{$ext}" );
					$this->branchedExtensions[$ext] = $status;
				} catch(Exception $e) {
					$this->branchedExtensions[$ext] = false;
					$this->abortSavingState();
				}

			}
		}
		foreach( $this->branchedSkins as $skin => $status) {
			if ($status === null) {
				try {
					$status = $this->branchRepo( "skins/{$skin}" );
					$this->branchedSkins[$skin] = $status;
				} catch(Exception $e) {
					$this->branchedExtensions[$ext] = false;
					$this->abortSavingState();
				}
			}
		}
		try {
			$this->branchRepo( 'vendor' );
			$this->branchWmf( $clonePath );
		} catch(Exception $e) {
			$this->abortSavingState();
		}
		if ($this->logOnly){
			$cli->lightGray('Command Log:')->br();
			$cli->border('=');
			$lines = join("\n", $this->cmdLog);
			$this->cli->darkGray($lines)->br();
		}
	}

	function setupBuildDirectory() {
		$resume = $this->cli->arguments->defined('resume');
		echo "is resume? $resume\n";
		# Create a temporary build directory
		if (file_exists($this->buildDir) && !$resume) {
			$this->runCmd( 'rm', '-rf', '--', $this->buildDir );
		}
		if (!mkdir($this->buildDir) && !$resume) {
			$this->croak( "Unable to create build directory {$this->buildDir}" );
		}
		$this->chdir( $this->buildDir );
	}

	function createBranch( $branchName, $doPush=true ) {
		$this->runCmd( 'git', 'checkout', '-q', '-b', $branchName );

		$this->fixGitReview();
		$this->runWriteCmd( 'git', 'commit', '-a', '-q', '-m', "Creating new {$branchName} branch" );
		$originUrl = trim(`git config --get remote.origin.url`);
		$originUrl = str_replace('https://gerrit.wikimedia.org/r/p/',
					 'ssh://gerrit.wikimedia.org:29418/',
					 $originUrl);
                $this->runCmd( 'git', 'remote', 'rm', 'origin' );
                $this->runCmd( 'git', 'remote', 'add', 'origin', $originUrl );
		if ($doPush == true) {
			$this->runWriteCmd( 'git', 'push', 'origin', $branchName );
		}
	}

	function branchRepo( $path  ) {
		$repo = basename( $path );
		$this->runCmd( 'git', 'clone', '-q', "{$this->baseRepoPath}/{$path}.git", $repo );
		$this->chdir( $repo );
		$newVersion = $this->branchPrefix . $this->newVersion;

		if ( isset( $this->branchedSubmodules[$path] ) ) {
			$this->createBranch( $newVersion, false );
			foreach ( (array)$this->branchedSubmodules[$path] as $submodule ) {
				$this->runCmd( 'git', 'submodule', 'update', '--init', $submodule );
				$this->chdir( $submodule );
				$this->createBranch( $newVersion );
				// Get us back to the repo directory by first going to the build directory,
				// then into the repo from there. chdir( '..' ) doesn't work because the submodule
				// may be inside a subdirectory
				$this->chdir( $this->buildDir );
				$this->chdir( $repo );
				$this->runCmd('git', 'add', $submodule);
			}
			$this->runCmd('git', 'commit', '-q', '--amend', '-m', "Creating new {$newVersion} branch");
			$this->runWriteCmd( 'git', 'push', 'origin', $newVersion );
		} else {
			$this->createBranch( $newVersion, true );
		}
		$this->chdir( $this->buildDir );
		return true;
	}

	function branchWmf( $clonePath ) {
		# Clone the repository
		$oldVersion = $this->oldVersion == 'master' ? 'master' : $this->branchPrefix . $this->oldVersion;
		$path = $clonePath ? $clonePath : "{$this->baseRepoPath}/core.git";
		$this->runCmd( 'git', 'clone', '-q', $path, '-b', $oldVersion, 'wmf' );

		$this->chdir( 'wmf' );

		# If we cloned from somewhere other than SSH, update remotes
		# and make sure our clone is up to date with origin
		if( $clonePath ) {
			$this->runCmd( 'git', 'remote', 'rm', 'origin' );
			$this->runCmd( 'git', 'remote', 'add', 'origin', "{$this->baseRepoPath}/core.git" );
			$this->runCmd( 'git', 'pull', '-q', '--ff-only', 'origin', $oldVersion );
		}

		# Look for the extensions we want to preserve the old branch's state
		$preservedRefs = array();
		foreach( $this->specialExtensions as $name => $copy ) {
			if( $copy === true ) {
				if( $this->oldVersion == 'master' ) {
					// There's nothing to copy in this instance, if you're trying
					// pin while oldVersion is master then use sha1's instead of true
					continue;
				} elseif( file_exists( "extension/$name" ) ) {
					$preservedRefs[$name] = file_get_contents( "extensions/$name" );
				} else {
					$this->croak( "Extension ($name) wants to copy from the old branch "
						. "but it doesn't exist there. Check configuration." );
				}
			} elseif( is_string( $copy ) ) {
				$preservedRefs[$name] = $copy;
			} else {
				$this->croak( "Extension ($name) misconfigured. Don't know how to proceed." );
			}
		}

		# Create a new branch from master and switch to it
		$newVersion = $this->branchPrefix . $this->newVersion;
		$this->runCmd( 'git', 'checkout', '-q', '-b', $newVersion );

		# Delete extensions/README and extensions/.gitignore if we branched master
		if( $this->oldVersion == 'master' ) {
			$this->runCmd( 'git', 'rm', '-q', "extensions/README", "extensions/.gitignore" );
		}

		# Add extension submodules
		foreach (
			array_merge( array_keys( $this->specialExtensions ), array_keys($this->branchedExtensions) )
				as $name ) {
			if( in_array( $name, $this->branchedExtensions ) ) {
				$this->runCmd( 'git', 'submodule', 'add', '-b', $newVersion, '-q',
					"{$this->anonRepoPath}/extensions/{$name}.git", "extensions/$name" );
			} else {
				$this->runCmd( 'git', 'submodule', 'add', '-q',
					"{$this->anonRepoPath}/extensions/{$name}.git", "extensions/$name" );
			}
			if( isset( $preservedRefs[$name] ) ) {
				$this->chdir( "extensions/$name" );
				$this->runCmd( 'git', 'remote', 'update' );
				$this->runCmd( 'git', 'checkout', '-q', $preservedRefs[$name] );
				$this->chdir( "../.." );
			}
		}

		# Add skin submodules
		foreach ( $this->branchedSkins as $name => $status) {
			$this->runCmd( 'git', 'submodule', 'add', '-f', '-b', $newVersion, '-q',
				"{$this->anonRepoPath}/skins/{$name}.git", "skins/$name" );
		}

		# Add vendor submodule
		$this->runCmd( 'git', 'submodule', 'add', '-f', '-b', $newVersion, '-q',
			"{$this->anonRepoPath}/vendor.git", 'vendor' );

		# Fix $wgVersion
		$this->fixVersion( "includes/DefaultSettings.php" );

		# Point gitreview defaultbranch at wmf/version
		$this->fixGitReview();

		# Do intermediate commit
		$this->runCmd( 'git', 'commit', '-a', '-q', '-m', "Creating new WMF {$this->newVersion} branch" );

		# Apply patches
		foreach ( $this->patches as $patch => $subpath ) {
			$this->runCmd( 'git', 'fetch', $this->baseRepoPath . '/' . $subpath, $patch );
			$this->runCmd( 'git', 'cherry-pick', 'FETCH_HEAD' );
		}

		$this->runWriteCmd( 'git', 'push', 'origin', 'wmf/' . $this->newVersion  );
	}

	function fixVersion( $fileName ) {
		$s = file_get_contents( $fileName );
		$s = preg_replace( '/^( \$wgVersion \s+ = \s+ )  [^;]*  ( ; \s* ) $/xm',
			"\\1'{$this->newVersion}'\\2", $s );
		file_put_contents( $fileName, $s );
	}

	function fixGitReview() {
		$orig = file_get_contents( ".gitreview" );
		$lines = explode("\n", $orig);
		$result = array();
		foreach ($lines as $line) {
	       $line = explode("=",$line,2);
	       $line[0] = trim($line[0]);
	       if (count($line) == 1) {
               $result[] = $line[0];
	       } else {
               if ($line[0] == 'defaultbranch') {
	               $line[1] = "{$this->branchPrefix}{$this->newVersion}";
               }
               $result[] = join('=', $line);
	       }
		}

		$result = join("\n",$result);
		if ($orig == $result) {
			// this is essentially just a dummy change so that there is
			// guaranteed to be some change to commit.
			// Without this, the commit fails sometimes and breaks everything.
			$result .= "\n# Branched at ".date('Y-m-d H:i:s');
		}

		file_put_contents( ".gitreview", $result );
	}
}