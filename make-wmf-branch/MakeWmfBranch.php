<?php

class MakeWmfBranch {
	var $dryRun;
	var $newVersion, $oldVersion, $buildDir;
	var $specialExtensions, $branchedExtensions, $branchedSkins, $patches;
	var $baseRepoPath, $anonRepoPath;
	var $noisy;

	function __construct( $newVersion, $oldVersion ) {
		$this->newVersion = $newVersion;
		$this->oldVersion = $oldVersion;
		$codeDir = dirname( __FILE__ );
		$buildDir = sys_get_temp_dir() . '/make-wmf-branch';

		require( "{$codeDir}/default.conf" );
		if ( file_exists( "{$codeDir}/local.conf" ) ) {
			require( "{$codeDir}/local.conf" );
		}

		$this->dryRun = $dryRun;
		$this->buildDir = $buildDir;
		$this->branchedExtensions = $branchedExtensions;
		$this->branchedSubmodules = $branchedSubmodules;
		$this->branchedSkins = $branchedSkins;
		$this->specialExtensions = $specialExtensions;
		$this->noisy = $noisy;
		$this->patches = $patches;
		$this->baseRepoPath = $baseRepoPath;
		$this->anonRepoPath = $anonRepoPath;
		$this->branchPrefix = $branchPrefix;
	}

	function runCmd( /*...*/ ) {
		$args = func_get_args();
		if( $this->noisy && in_array( "-q", $args ) ) {
			$args = array_diff( $args, array( "-q" ) );
		}
		$encArgs = array_map( 'escapeshellarg', $args );
		$cmd = implode( ' ', $encArgs );

		$attempts = 0;
		do {
			echo "$cmd\n";
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
			echo "[dry-run] $cmd\n";
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
		fwrite( STDERR, "$msg\n" );
		exit( 1 );
	}

	function execute( $clonePath ) {
		$this->setupBuildDirectory();
		foreach( $this->branchedExtensions as $ext ) {
			$this->branchRepo( "extensions/{$ext}" );
		}
		foreach( $this->branchedSkins as $skin ) {
			$this->branchRepo( "skins/{$skin}" );
		}
		$this->branchRepo( 'vendor' );
		$this->branchWmf( $clonePath );
	}

	function setupBuildDirectory() {
		# Create a temporary build directory
		if ( file_exists( $this->buildDir ) ) {
			$this->runCmd( 'rm', '-rf', '--', $this->buildDir );
		}
		if ( !mkdir( $this->buildDir ) ) {
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
			array_merge( array_keys( $this->specialExtensions ), $this->branchedExtensions )
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
		foreach ( $this->branchedSkins as $name ) {
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
			// git fetch ssh://reedy@gerrit.wikimedia.org:29418/mediawiki/core refs/changes/06/7606/1 && git cherry-pick FETCH_HEAD
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
		$s = file_get_contents( ".gitreview" );
		$s = str_replace( "defaultbranch=master", "defaultbranch={$this->branchPrefix}{$this->newVersion}", $s );
		file_put_contents( ".gitreview", $s );
	}
}

