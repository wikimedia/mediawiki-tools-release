<?php

/**
 * Class to handle the OS and git interface.
 *
 * Copyright (C) 2019  Wikimedia Foundation, Inc.
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * @author Mark A. Hershberger <mah@nichework.com>
 */

namespace Wikimedia\Release;

use Christiaan\StreamProcess\StreamProcess;
use Exception;
use Hexmode\PhpGerrit\Entity\BranchInfo;
use Hexmode\PhpGerrit\Entity\BranchInput;
use Hexmode\PhpGerrit\GerritRestAPI;
use Psr\Log\LoggerInterface;
use React\EventLoop\Factory as LoopFactory;

class Control {
	/** @var LoggerInterface */
	protected $logger;
	/** @var array */
	protected $dirs;
	/** @var bool */
	protected $dryRun;
	/** @var string */
	protected $output;
	/** @var bool */
	protected $storeOutput;
	/** @var Branch */
	protected $brancher;
	/** @var ?string */
	protected $localGitURL = null;
	/** @var ?string */
	protected $gerritURL = null;
	/** @var ?GerritRestAPI */
	protected $gerrit = null;
	/** @var array */
	protected $branchCache;

	/**
	 * @param LoggerInterface $logger
	 * @param bool $dryRun
	 * @param Branch $brancher
	 */
	public function __construct(
		LoggerInterface $logger,
		bool $dryRun,
		Branch $brancher
	) {
		$this->logger = $logger;
		$this->dryRun = $dryRun;
		$this->dirs = [];
		$this->output = "";
		$this->storeOutput = false;
		$this->brancher = $brancher;
		$this->branchCache = [];
	}

	/**
	 * Set up a gerrit repo
	 *
	 * @param string $url
	 */
	public function setGerritURL( string $url ): void {
		$this->gerritURL = $url;
		$this->gerrit = new GerritRestAPI( $url );
		if ( $this->dryRun ) {
			$this->gerrit->setReadOnly();
		}
	}

	/**
	 * @param ?string|null $url = null
	 */
	public function setLocalGitURL( ?string $url = null ): void {
		$this->localGitURL = $url;
	}

	/**
	 * Display error message and die
	 *
	 * @param string $msg
	 * @return never-return
	 */
	protected function croak( string $msg ): void {
		$this->brancher->croak( $msg );
	}

	/**
	 * Change dir or die if there is a problem.
	 *
	 * @param string $dir
	 */
	public function chdir( string $dir ): void {
		$this->dirs[] = getcwd();
		if ( !chdir( $dir ) ) {
			$this->croak( "Unable to change working directory to $dir" );
		}
		$this->logger->debug( "$ cd $dir" );
	}

	/**
	 * Change dir to the previous directory.
	 */
	public function popdir(): void {
		$dir = array_pop( $this->dirs );
		if ( !chdir( $dir ) ) {
			$this->croak( "Unable to return to the $dir directory" );
		}
		$this->logger->debug( "$ cd $dir" );
	}

	/**
	 * Return the output of git status --porcelain
	 * be dealt with
	 *
	 * @return string
	 */
	public function getChanges(): string {
		return $this->cmdOutNoTrim( 'git', 'status', '--porcelain' );
	}

	/**
	 * Determine if a branch already exists for this repository.
	 *
	 * @param string $repo to check
	 * @param string $branch to check for
	 * @return bool
	 */
	public function hasBranch( string $repo, string $branch ): bool {
		$branchList = $this->getBranches( $repo );
		$res = in_array( $branch, $branchList );
		if ( $res ) {
			$this->logger->debug( "Branch ($branch) exists in ($repo)" );
		} else {
			$this->logger->debug( "Branch ($branch) does not "
								. "exist in ($repo)" );
		}
		return $res;
	}

	/** Return the list of branches for this repository.
	 *
	 * @param string $repo to get
	 * @return array<int|string> of branches
	 */
	public function getBranches( string $repo ): array {
		$branchInfo = $this->getBranchInfo( [ $repo ] );
		return $branchInfo[$repo];
	}

	/**
	 * Get branch info for a list of repositories
	 *
	 * @param array $repo
	 * @return array
	 */
	public function getBranchInfo( array $repo ): array {
		if ( !$this->gerrit ) {
			$this->croak( "Please set up the Gerrit remote first!" );
		}
		$ret = [];
		foreach ( array_filter( $repo ) as $project ) {
			if ( !isset( $this->branchCache[$project] ) ) {
				$this->logger->info( "Get branch information on $project." );
				$this->branchCache[$project]
					= $this->gerrit->listBranches( $project );
			}
			$ret[$project] = $this->branchCache[$project];
		}
		return $ret;
	}

	/**
	 * Handle server-side branching
	 *
	 * @param string $repo
	 * @param string $branchFrom where to base the branch from
	 * @param string $newBranch name of new branch
	 * @return BranchInfo
	 */
	public function createBranch(
		string $repo,
		string $branchFrom,
		string $newBranch
	): BranchInfo {
		if ( !$this->gerrit ) {
			$this->croak( "Please set up the Gerrit remote first!" );
		}
		$branch = new BranchInput(
			[ 'ref' => $newBranch, 'revision' => $branchFrom ]
		);
		return $this->gerrit->createBranch( $repo, $branch );
	}

	/**
	 * Checkout a branch of the reposistory
	 *
	 * @param string $repo primary repo
	 * @param string $branch submodule'd repo
	 * @param string $loc is sthe location on disk
	 */
	public function clone(
		string $repo,
		string $branch,
		string $loc
	): void {
		$repoURL = $this->makeRepoURL( $repo );
		if ( $this->cmd( "git", "clone", "-b", $branch, $repoURL, $loc ) ) {
			$this->croak( "Trouble cloning!" );
		}
		$realRepo = $this->makeRepoURL( $repo, false );
		if ( $repoURL !== $realRepo ) {
			$this->chdir( $loc );
			if ( $this->cmd( "git", "remote", "set-url", "origin", $realRepo ) ) {
				$this->croak( "Trouble setting remote!" );
			}
			if ( $this->cmd( "git", "pull", "origin" ) ) {
				$this->croak( "Couldn't update local repo!" );
			}
			$this->popdir();
		}
	}

	/**
	 * Ensure that the given directory is completely empty by removing
	 * it and recreating it.
	 *
	 * @param string $dir
	 * @throws Exception
	 */
	public function ensureEmptyDir( string $dir ): void {
		if ( $this->cmd( "rm", "-rf", $dir ) ) {
			throw new Exception( "Could not erase $dir!" );
		}
		if ( !mkdir( $dir, 0722, true ) ) {
			throw new Exception( "Could not create $dir!" );
		}
	}

	/**
	 * Get a fully qualified URL for the gerrit repo.
	 *
	 * @param string $repo in gerrit
	 * @param bool $useLocal use a local copy
	 * @return string URL
	 */
	public function makeRepoURL( string $repo, bool $useLocal = true ): string {
		if ( !$this->gerritURL ) {
			$this->croak( "Please set up the Gerrit URL first!" );
		}
		$base = $this->gerritURL;
		if ( $this->localGitURL && $useLocal ) {
			$base = $this->localGitURL;
		}
		return $base . "/" . $repo;
	}

	/**
	 * Determine if a submodule exists
	 *
	 * @param string $repo primary repo
	 * @param string $subRepo submodule'd repo
	 * @param string $loc location repo should be as a subdir
	 * @return bool
	 */
	public function hasSubmodule(
		string $repo,
		string $subRepo,
		string $loc
	): bool {
	}

	/**
	 * Set up a submodule to a repo
	 *
	 * @param string $repo primary repo
	 * @param string $subRepo submodule'd repo
	 * @param string $loc location repo should be as a subdir
	 * @return bool
	 */
	public function addSubmodule(
		string $repo,
		string $subRepo,
		string $loc
	): bool {
	}

	/**
	 * Try to run a command and die if it fails
	 *
	 * @param array ...$args
	 * @return int exit code
	 */
	public function runCmd( ...$args ): int {
		if ( is_array( $args[0] ) ) {
			$args = $args[0];
		}

		$attempts = 0;
		do {
			if ( $attempts ) {
				$this->logger->warning( "sleeping for 5s" );
				sleep( 5 );
			}
			$ret = $this->cmd( $args );
		} while ( $ret !== 0 && ++$attempts <= 5 );
		return $ret;
	}

	/**
	 * Return what the command sends to stdout instead of just
	 * printing it. Stderr is still printed.
	 *
	 * @param array ...$args
	 * @return string
	 */
	public function cmdOut( ...$args ): string {
		$this->storeOutput = true;
		$this->output = '';
		$this->cmd( $args );
		$this->storeOutput = false;
		return trim( $this->output );
	}

	/**
	 * Like cmdOut, but the output isn't put through trim.
	 *
	 * @param array ...$args
	 * @return string
	 */
	public function cmdOutNoTrim( ...$args ): string {
		$this->storeOutput = true;
		$this->output = '';
		$this->cmd( $args );
		$this->storeOutput = false;
		return $this->output;
	}

	/**
	 * Conditionally (if not a dry run) run a command.
	 *
	 * @param array ...$args
	 * @return int
	 */
	public function runWriteCmd( ...$args ): int {
		$ret = 0;
		if ( $this->dryRun ) {
			$this->logger->debug( "[dry-run] " . implode( ' ', $args ) );
		} else {
			$ret = $this->runCmd( $args );
		}
		return $ret;
	}

	/**
	 * Run a command
	 *
	 * @param array ...$args
	 * @return int (exit code)
	 */
	public function cmd( ...$args ): int {
		if ( is_array( $args[0] ) ) {
			$args = $args[0];
		}

		$this->logger->debug( "$ " . implode( ' ', $args ) );

		$loop = LoopFactory::create();
		$proc = new StreamProcess(
			implode( ' ', array_map( 'escapeshellarg', $args ) )
		);

		$loop->addReadStream(
			$proc->getReadStream(),
			/** @param resource $stream */
			function ( $stream ) use ( $loop ): void {
				$out = fgets( $stream );
				if ( $out !== false ) {
					if ( $this->storeOutput ) {
						$this->output .= $out;
					}
					$this->logger->debug( $out );
				} else {
					$loop->stop();
				}
			}
		);
		$loop->addReadStream(
			$proc->getErrorStream(),
			/** @param resource $stream */
			function ( $stream ): void {
				$out = fgets( $stream );
				if ( $out !== false ) {
					$this->logger->warning( $out );
				}
			}
		);

		$loop->run();
		return $proc->close();
	}

	/**
	 * Not yet implemented
	 *
	 * @param string $branch
	 */
	public function checkout( string $branch ): void {
		throw new \Exception( "Implement me! " . __METHOD__ );
	}

	/**
	 * Not yet implemented
	 *
	 * @param string $topRepo
	 * @param string $repo
	 * @param string $dir
	 */
	public function checkoutSubmodule( string $topRepo, string $repo, string $dir ): void {
		throw new \Exception( "Implement me! " . __METHOD__ );
	}

	/**
	 * Not yet implemented
	 *
	 * @param string $branch
	 */
	public function push( string $branch ): void {
		throw new \Exception( "Implement me! " . __METHOD__ );
	}
}
