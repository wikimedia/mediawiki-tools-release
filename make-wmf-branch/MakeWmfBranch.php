<?php

class MakeWmfBranch {
	public $dryRun;
	public $newVersion, $oldVersion, $buildDir;
	public $specialExtensions, $branchedExtensions, $branchedSkins, $patches;
	public $repoPath;
	public $noisy;

	function __construct( $newVersion, $oldVersion ) {
		$this->newVersion = $newVersion;
		$this->oldVersion = $oldVersion;
		$buildDir = sys_get_temp_dir() . '/make-wmf-branch';

		require __DIR__ . '/default.conf';

		$branchLists = json_decode(
			file_get_contents( __DIR__ . '/config.json' ),
			true
		);

		// This comes after we load all the default configuration
		// so it is possible to override default.conf and $branchLists
		if ( file_exists( __DIR__ . '/local.conf' ) ) {
			require __DIR__ . '/local.conf';
		}

		$this->dryRun = $dryRun;
		$this->buildDir = $buildDir;
		$this->branchedExtensions = $branchLists['extensions'];
		$this->branchedSubmodules = $branchLists['submodules'];
		$this->branchedSkins = $branchLists['skins'];
		$this->specialExtensions = $branchLists['special_extensions'];
		$this->alreadyBranched = array();
		$this->noisy = $noisy;
		$this->patches = $patches;
		$this->repoPath = $repoPath;
		$this->branchPrefix = $branchPrefix;
	}

	/**
	 * setup an alreadyBranched array that has the names of all extensions
	 * up-to the extension from which we would like to start branching
	 *
	 * @param String/null $extName - name of extension from which to start branching
	 */
	function setStartExtension( $extName ) {
		if ( $extName === null ) {
			return;
	 }

		$foundKey = false;
		foreach ( array(
			$this->branchedExtensions,
			$this->branchedSkins,
			array( 'vendor' ),
		) as $branchedArr ) {
			$key = array_search( $extName, $branchedArr );

			if ( $key !== false ) {
				array_splice( $branchedArr, $key );
				$foundKey = true;
			}

			$this->alreadyBranched = array_merge(
				$this->alreadyBranched,
				$branchedArr
			);

			if ( $foundKey ) {
				break;
	  }
		}

		if ( !$foundKey ) {
			$this->croak(
				"Could not find extension '{$extName}' in any branched Extension list"
			);
	 }

		// Should make searching array easier
		$this->alreadyBranched = array_flip( $this->alreadyBranched );
	}

	function runCmd( /*...*/ ) {
		$args = func_get_args();
		if ( $this->noisy && in_array( "-q", $args ) ) {
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
		$red = `tput setaf 1`;
		$reset = `tput sgr0`;

		fprintf( STDERR, "[{$red}ERROR{$reset}] %s\n", $msg );
		exit( 1 );
	}

	function execute( $clonePath ) {
		$this->setupBuildDirectory();
		foreach ( $this->branchedExtensions as $ext ) {
			$this->branchRepo( "extensions/{$ext}" );
		}
		foreach ( $this->branchedSkins as $skin ) {
			$this->branchRepo( "skins/{$skin}" );
		}
		$this->branchRepo( 'vendor' );
		$this->branchWmf( $clonePath );
	}

	function setupBuildDirectory() {
		# Create a temporary build directory
		$this->teardownBuildDirectory();
		if ( !mkdir( $this->buildDir ) ) {
			$this->croak( "Unable to create build directory {$this->buildDir}" );
		}
		$this->chdir( $this->buildDir );
	}

	function teardownBuildDirectory() {
		if ( file_exists( $this->buildDir ) ) {
			$this->runCmd( 'rm', '-rf', '--', $this->buildDir );
		}
	}

	function createBranch( $branchName, $doPush=true ) {
		$this->runCmd( 'git', 'checkout', '-q', '-b', $branchName );

		$this->fixGitReview();
		$this->runWriteCmd( 'git', 'commit', '-a', '-q', '-m', "Creating new {$branchName} branch" );
		if ( $doPush == true ) {
			$this->runWriteCmd( 'git', 'push', 'origin', $branchName );
		}
	}

	function branchRepo( $path ) {
		$repo = basename( $path );

		// repo has already been branched, so just bail out
		if ( isset( $this->alreadyBranched[$repo] ) ) {
			return;
	 }

		$this->runCmd( 'git', 'clone', '-q', "{$this->repoPath}/{$path}.git", $repo );
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
				$this->runCmd( 'git', 'add', $submodule );
			}
			$this->runCmd( 'git', 'commit', '-q', '--amend', '-m', "Creating new {$newVersion} branch" );
			$this->runWriteCmd( 'git', 'push', 'origin', $newVersion );
		} else {
			$this->createBranch( $newVersion, true );
		}
		$this->chdir( $this->buildDir );
	}

	function branchWmf( $clonePath ) {
		# Clone the repository
		$oldVersion = $this->oldVersion == 'master' ? 'master' : $this->branchPrefix . $this->oldVersion;
		$path = $clonePath ? $clonePath : "{$this->repoPath}/core.git";
		$this->runCmd( 'git', 'clone', '-q', $path, '-b', $oldVersion, 'wmf' );

		$this->chdir( 'wmf' );

		# make sure our clone is up to date with origin
		if ( $clonePath ) {
			$this->runCmd( 'git', 'pull', '-q', '--ff-only', 'origin', $oldVersion );
		}

		# Create a new branch from master and switch to it
		$newVersion = $this->branchPrefix . $this->newVersion;
		$this->runCmd( 'git', 'checkout', '-q', '-b', $newVersion );

		# Delete extensions/README and extensions/.gitignore if we branched master
		if ( $this->oldVersion == 'master' ) {
			$this->runCmd( 'git', 'rm', '-q', "extensions/README", "extensions/.gitignore" );
		}

		# Add extension submodules
		foreach (
			array_merge( array_keys( $this->specialExtensions ), $this->branchedExtensions )
				as $name ) {

			$submoduleBranch = $newVersion;

			if ( isset( $this->specialExtensions[$name] ) ) {
				$submoduleBranch = $this->specialExtensions[$name];
	  }

			$this->runCmd( 'git', 'submodule', 'add', '-b', $submoduleBranch, '-q',
				"{$this->repoPath}/extensions/{$name}.git", "extensions/$name" );
		}

		# Add skin submodules
		foreach ( $this->branchedSkins as $name ) {
			$this->runCmd( 'git', 'submodule', 'add', '-f', '-b', $newVersion, '-q',
				"{$this->repoPath}/skins/{$name}.git", "skins/$name" );
		}

		# Add vendor submodule
		$this->runCmd( 'git', 'submodule', 'add', '-f', '-b', $newVersion, '-q',
			"{$this->repoPath}/vendor.git", 'vendor' );

		# Fix $wgVersion
		$this->fixVersion( "includes/DefaultSettings.php" );

		# Point gitreview defaultbranch at wmf/version
		$this->fixGitReview();

		# Do intermediate commit
		$this->runCmd( 'git', 'commit', '-a', '-q', '-m', "Creating new WMF {$this->newVersion} branch" );

		# Apply patches
		foreach ( $this->patches as $patch => $subpath ) {
			// git fetch https://gerrit.wikimedia.org/mediawiki/core
			// refs/changes/06/7606/1 && git cherry-pick FETCH_HEAD
			$this->runCmd( 'git', 'fetch', $this->repoPath . '/' . $subpath, $patch );
			$this->runCmd( 'git', 'cherry-pick', 'FETCH_HEAD' );
		}

		$this->runWriteCmd(
			'git', 'push', 'origin', 'wmf/' . $this->newVersion );
	}

	function fixVersion( $fileName ) {
		$s = file_get_contents( $fileName );
		$s = preg_replace( '/^( \$wgVersion \s+ = \s+ )  [^;]*  ( ; \s* ) $/xm',
			"\\1'{$this->newVersion}'\\2", $s );
		file_put_contents( $fileName, $s );
	}

	function fixGitReview() {
		$lines = file( '.gitreview', FILE_IGNORE_NEW_LINES );
		$outputFile = array();
		$changed = false;

		foreach ( $lines as $line ) {
			$arr = explode( '=', $line );

			if ( count( $arr ) < 2 ) {
				$outputFile[] = $line;
				continue;
			}

			list( $k, $v ) = $arr;

			if ( trim( $k ) === 'defaultbranch' ) {
				$v = "{$this->branchPrefix}{$this->newVersion}";
				$changed = true;
			}

			$outputFile[] = implode( '=', array( $k, $v ) );
		}

		$final = implode( "\n", $outputFile );
		$final .= "\n";

		if ( !$changed ) {
			$final .= '# Updated ' . date( 'c' ) . "\n";
	 }

		file_put_contents( '.gitreview', $final );
	}
}
