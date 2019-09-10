<?php

class MakeWmfBranch {
	public $dryRun;
	public $newVersion, $oldVersion, $buildDir;
	public $specialExtensions, $branchedExtensions;
	public $repoPath;
	public $noisy;

	/**
	 * @param string $newVersion Version for the new branch.
	 * @param string $oldVersion Version to make the new branch from. If
	 * evaluated to false, would fallback to 'master'.
	 */
	public function __construct( $newVersion, $oldVersion ) {
		$this->newVersion = $newVersion;
		$this->oldVersion = $oldVersion ?: 'master';
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
		$this->specialExtensions = $branchLists['special_extensions'];
		$this->alreadyBranched = array();
		$this->noisy = $noisy;
		$this->repoPath = $repoPath;
		$this->branchPrefix = $branchPrefix;
	}

	/**
	 * setup an alreadyBranched array that has the names of all extensions
	 * up-to the extension from which we would like to start branching
	 *
	 * @param string|null $extName - name of extension from which to start branching
	 */
	public function setStartExtension( $extName ) {
		if ( $extName === null ) {
			return;
		}

		$foundKey = false;

		// Create a copy of $this->branchedExtensions that can be mangled
		foreach ( array( $this->branchedExtensions ) as $branchedArr ) {
			// Find the index of the start extension in the branchedExtension list
			$key = array_search( $extName, $branchedArr );

			// Remove all extensions that have already been branched from $branchedArr
			// by using the index of the --continue-from extension as an offset
			if ( $key !== false ) {
				array_splice( $branchedArr, $key );
				$foundKey = true;
			}

			// $this->alreadyBranched = $branchedArr, gently
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

	// @codingStandardsIgnoreStart
	function runCmd( /*...*/ ) {
	// @codingStadnardsIgnoreEnd
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

	// @codingStandardsIgnoreStart
	function runWriteCmd( /*...*/ ) {
	// @codingStadnardsIgnoreEnd
		$args = func_get_args();
		if ( $this->dryRun ) {
			$encArgs = array_map( 'escapeshellarg', $args );
			$cmd = implode( ' ', $encArgs );
			echo "[dry-run] $cmd\n";
		} else {
			call_user_func_array( array( $this, 'runCmd' ), $args );
		}
	}

	/**
	 * @param string $dir Directory to change directory to.
	 */
	function chdir( $dir ) {
		if ( !chdir( $dir ) ) {
			$this->croak( "Unable to change working directory\n" );
		}
		echo "cd $dir\n";
	}

	/**
	 * Emit a colored error message ($msg) and exit(1).
	 *
	 * @param string $msg Message to colorized. Written to stderr.
	 */
	function croak( $msg ) {
		$red = `tput setaf 1`;
		$reset = `tput sgr0`;

		fprintf( STDERR, "[{$red}ERROR{$reset}] %s\n", $msg );
		exit( 1 );
	}

	/**
	 * @param string $clonePath Path in which to clone mediawiki/core.
	 */
	function execute( $clonePath ) {
		$this->setupBuildDirectory();
		foreach ( $this->branchedExtensions as $ext ) {
			$this->branchRepo( $ext );
		}
		foreach ( $this->specialExtensions as $ext => $branch ) {
			$this->branchRepo( $ext, $branch );
		}
		$this->branchWmf( $clonePath );
	}

	/**
	 * Attempt to create the build directory and chdir() to it.
	 */
	function setupBuildDirectory() {
		# Create a temporary build directory
		$this->teardownBuildDirectory();
		if ( !mkdir( $this->buildDir ) ) {
			$this->croak( "Unable to create build directory {$this->buildDir}" );
		}
		$this->chdir( $this->buildDir );
	}

	/**
	 * Erase the buildDir if it exists.
	 */
	function teardownBuildDirectory() {
		if ( file_exists( $this->buildDir ) ) {
			$this->runCmd( 'rm', '-rf', '--', $this->buildDir );
		}
	}

	/**
	 * @param string $branchName Name of branch to create and push.
	 */
	function createBranch( $branchName ) {
		$this->runCmd( 'git', 'checkout', '-q', '-b', $branchName );
		$this->runWriteCmd( 'git', 'push', 'origin', $branchName );
	}

	/**
	 * @param string $path Path of the repository to branch.
	 * @param string $branch Branch to clone Default: 'master'
	 */
	function branchRepo( $path , $branch = 'master' ) {
		// repo has already been branched, so just bail out
		if ( isset( $this->alreadyBranched[$path] ) ) {
			return;
		}

		$repo = basename( $path );

		$this->runCmd(
			'git',
			'clone',
			'-q',
			'--branch',
			$branch,
			'--depth',
			'1',
			"{$this->repoPath}/{$path}", $repo
		);

		$this->chdir( $repo );
		$newVersion = $this->branchPrefix . $this->newVersion;

		if ( isset( $this->branchedSubmodules[$path] ) ) {
			foreach ( (array)$this->branchedSubmodules[$path] as $submodule ) {
				$this->runCmd( 'git', 'submodule', 'update', '--init', $submodule );
				$this->chdir( $submodule );
				$this->createBranch( $newVersion );
				// Get us back to the repo directory by first going to the build directory,
				// then into the repo from there. chdir( '..' ) doesn't work because the submodule
				// may be inside a subdirectory
				$this->chdir( $this->buildDir );
				$this->chdir( $repo );
			}
		}
		$this->createBranch( $newVersion );
		$this->chdir( $this->buildDir );
	}

	/**
	 * @param string $clonePath Path in which to clone mediawiki/core.
	 */
	function branchWmf( $clonePath ) {
		# Clone the repository
		$oldVersion = $this->oldVersion == 'master' ? 'master' : $this->branchPrefix . $this->oldVersion;
		$path = $clonePath ? $clonePath : "{$this->repoPath}/core";
		$this->runCmd( 'git', 'clone', '-q', $path, '-b', $oldVersion, 'wmf' );

		$this->chdir( 'wmf' );

		# make sure our clone is up to date with origin
		if ( $clonePath ) {
			$this->runCmd( 'git', 'pull', '-q', '--ff-only', 'origin', $oldVersion );
		}

		# Create a new branch from master and switch to it
		$newVersion = $this->branchPrefix . $this->newVersion;
		$this->runCmd( 'git', 'checkout', '-q', '-b', $newVersion );

		# Add extensions/skins/vendor
		foreach ( $this->branchedExtensions as $name ) {
			$this->runCmd( 'git', 'submodule', 'add', '-f', '-b', $newVersion, '-q',
				"{$this->repoPath}/{$name}", $name );
		}

		# Add extension submodules
		foreach ( $this->specialExtensions as $name => $specialBranch ) {
			$this->runCmd( 'git', 'submodule', 'add', '-f', '-b', $newVersion, '-q',
			"{$this->repoPath}/{$name}", $name );
		}

		# Fix $wgVersion
		$this->fixVersion( "includes/DefaultSettings.php" );

		# Do intermediate commit
		$this->runCmd( 'git', 'commit', '-a', '-q', '-m', "Creating new WMF {$this->newVersion} branch" );

		$this->runWriteCmd(
			'git', 'push', 'origin', 'wmf/' . $this->newVersion );
	}

	/**
	 * @param string $fileName Name of file to inline replace $wgVersion value.
	 */
	function fixVersion( $fileName ) {
		$s = file_get_contents( $fileName );
		$s = preg_replace( '/^( \$wgVersion \s+ = \s+ )  [^;]*  ( ; \s* ) $/xm',
			"\\1'{$this->newVersion}'\\2", $s );
		file_put_contents( $fileName, $s );
	}
}
