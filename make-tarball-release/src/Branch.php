<?php

/*
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

use hanneskod\classtools\Iterator\ClassIterator;
use Psr\Log\LoggerInterface;
use splitbrain\phpcli\Options;
use splitbrain\phpcli\UsageException as Usage;
use Symfony\Component\Finder\Finder;

abstract class Branch {
	private const MWREPO = "mediawiki/core";

	/** @var string */
	protected $newVersion;
	/** @var string */
	protected $oldVersion;
	/** @var string */
	protected $buildDir;
	/** @var array */
	protected $specialExtensions;
	/** @var array */
	protected $branchedSubmodules;
	/** @var array */
	protected $branchedExtensions;
	/** @var string */
	protected $repoPath;
	/** @var bool */
	protected $noisy;
	/** @var LoggerInterface */
	protected $logger;
	/** @var string */
	protected $branchPrefix;
	/** @var string */
	protected $clonePath;
	/** @var array */
	protected $alreadyBranched;
	/** @var Control */
	protected $control;
	/** @var string */
	protected $branchFrom;
	/** @var bool */
	protected $dryRun;
	/** @var ?string */
	protected $localGitURL;

	/**
	 * How will we refer to this branch
	 *
	 * @return string
	 */
	abstract public static function getShortname() :string;

	/**
	 * Tell the user what kind of branches this class handles
	 *
	 * @return string
	 */
	abstract public static function getDescription() :string;

	/**
	 * Get a directory where we can work.
	 *
	 * @return string
	 */
	abstract public function getWorkDir() :string;

	/**
	 * Get the branch prefix default;
	 *
	 * @return string
	 */
	abstract protected function getBranchPrefix() :string;

	/**
	 * Get the git repo path
	 *
	 * @return string
	 */
	abstract public function getRepoPath() :string;

	/**
	 * Get the directory to put the branch in
	 *
	 * @return string
	 */
	abstract protected function getBranchDir() :string;

	/**
	 * Set up the build directory
	 *
	 * @return string dir
	 */
	abstract public function setupBuildDirectory() :string;

	/**
	 * Get the config.json file to use for this branch type
	 *
	 * @param string $dir
	 * @return string
	 */
	abstract protected function getConfigJson( string $dir ) :string;

	/**
	 * Set up the options for the command line program
	 *
	 * @param Options $opt
	 */
	public static function setupOptions( Options $opt ) :void {
		$opt->setHelp( "Create Branches" );
		$opt->setCommandHelp( "Specify one of the following branch styles:" );
		$opt->setCompactHelp();

		$types = self::getAvailableBranchTypes();
		foreach ( $types as $name => $desc ) {
			$opt->registerCommand( $name, $desc );
		}

		$opt->registerOption( 'new', 'New branch name.', 'n', 'name' );
		$opt->registerOption(
			'old', 'Old branch name. (default: master)', 'o', 'name'
		);
		$opt->registerOption( 'dry-run', 'Do everything but push.', 'd' );
		$opt->registerOption(
			'path', 'Path on Local disk from which to branch '
			. 'mediawiki-core.', 'p', 'path'
		);
		$opt->registerOption(
			'keep-tmp', 'Whether to keep files in /tmp after finishing. '
			. 'Default is to remove.', 'k'
		);
		$opt->registerOption(
			'local-git-repo', 'Full path to local git repo to act as git '
			. 'cache for Gerrit.', 'g', 'url'
		);
	}

	/**
	 * Get the list of available branches.
	 *
	 * @return array
	 */
	public static function getAvailableBranchTypes() :array {
		$finder = new Finder;
		$iter = new ClassIterator( $finder->in( __DIR__ ) );
		$thisClass = __CLASS__;
		$ret = [];

		foreach ( array_keys( $iter->getClassMap() ) as $classname ) {
			if (
				is_string( $classname ) &&
				$classname !== $thisClass &&
				get_parent_class( $classname ) === $thisClass
			) {
				$shortname = $classname::getShortname();
				$desc = $classname::getDescription();
				$ret[$shortname] = $desc;
			}
		}

		return $ret;
	}

	/**
	 * Factory of branches
	 *
	 * @param string $type of brancher to create
	 * @param Options $opt the user gave
	 * @param LoggerInterface $logger PSR3 Logger
	 * @return self
	 */
	public static function getBrancher(
		?string $type,
		Options $opt,
		LoggerInterface $logger
	) :self {
		if ( !$type ) {
			throw new Usage( "Please specify a branch type!" );
		}

		if ( !$opt->getOpt( 'new' ) ) {
			throw new Usage( "'-n' or '--new' must be set.\n" );
		}

		if ( !$opt->getCmd() ) {
			throw new Usage( "Please provide a branch type.\n" );
		}

		$class = __CLASS__ . "\\" . ucFirst( $type );
		if ( !class_exists( $class ) ) {
			throw new Usage( "$type is not a proper brancher!" );
		}

		$brancher = new $class(
			$opt->getOpt( "old", 'master' ),
			$opt->getOpt( 'branch-prefix', '' ),
			$opt->getOpt( 'new' ),
			$opt->getOpt( 'path', '' ),
			$opt->getOpt( 'dryRun', getenv( "dryRun" ) !== false ),
			// Should this just use old?
			$opt->getOpt( 'branchFrom', 'master' ),
			$logger
		);
		$brancher->setLocalGitURL( $opt->getOpt( 'local-git-repo', '' ) );

		if ( is_a( $brancher, self::class ) ) {
			return $brancher;
		}
		throw new Usage( "$type is not a proper brancher!" );
	}

	/**
	 * @param string $oldVersion
	 * @param string $branchPrefix
	 * @param string $newVersion
	 * @param string $clonePath
	 * @param bool $dryRun
	 * @param string $branchFrom
	 * @param LoggerInterface $logger
	 */
	public function __construct(
		string $oldVersion,
		string $branchPrefix,
		string $newVersion,
		string $clonePath,
		bool $dryRun,
		string $branchFrom,
		LoggerInterface $logger
	) {
		$this->oldVersion = $oldVersion;
		$this->branchPrefix = "";
		$this->newVersion = "master";
		if ( !$dryRun ) {
			$this->branchPrefix = $branchPrefix;
			$this->newVersion = $newVersion;
		}
		$this->clonePath = $clonePath;
		$this->logger = $logger;
		$this->branchFrom = $branchFrom;

		$this->repoPath = "";
		$this->buildDir = "";
		$this->noisy = false;
		$this->branchedExtensions = [];
		$this->branchedSubmodules = [];
		$this->alreadyBranched = [];
		$this->specialExtensions = [];
		$this->dryRun = $dryRun;
		$this->control = new Control( $logger, $dryRun, $this );
	}

	/**
	 * Set up the defaults for this branch type
	 *
	 * @param string $dir
	 */
	protected function setDefaults( string $dir ) :void {
		$repoPath = $this->getRepoPath();
		$branchPrefix = $this->getBranchPrefix();
		$buildDir = $this->getWorkDir();
		// Output git commands or not
		$noisy = false;
		// Push stuff or not
		$dryRun = false;

		if ( is_readable( $dir . '/default.conf' ) ) {
			require $dir . '/default.conf';
		}

		// This comes after we load all the default configuration
		// so it is possible to override default.conf and $branchLists
		if ( is_readable( $dir . '/local.conf' ) ) {
			require $dir . '/local.conf';
		}

		$this->control->setGerritURL( $repoPath );
		if ( $this->localGitURL ) {
			$this->control->setLocalGitURL( $this->localGitURL );
		}
		$this->repoPath = $repoPath;
		$this->branchPrefix = $branchPrefix;
		$this->dryRun = $this->dryRun ?? $dryRun;
		$this->noisy = $noisy;
		$this->clonePath = $this->clonePath ?? "{$this->repoPath}/core";
		$this->buildDir = $buildDir;
	}

	/**
	 * Set the repo url for a local copy of the git repo
	 *
	 * @param string $localGit
	 */
	public function setLocalGitURL( string $localGit ) :void {
		if ( $localGit === '' ) {
			return;
		}
		if ( substr( $localGit, 0, 1 ) !== '/' ) {
			throw new Usage( "Local git URL must be a path!" );
		}
		if ( !is_readable( $localGit ) ) {
			throw new Usage( "Local git URL must be readable!" );
		}
		$this->localGitURL = $localGit;
	}

	/**
	 * An extremely naive check of the schema.  Sends notices to the PSR3 logger.
	 *
	 * @param string $text
	 * @param array &$var
	 * @param string $file
	 */
	protected function stupidSchemaCheck(
		string $text, array &$var, string $file
	) :void {
		foreach (
			[ 'extensions', 'submodules', 'special_extensions' ] as $key
		) {
			if ( !isset( $var[$key] ) ) {
				$var[$key] = [];
				$this->logger->notice(
					"The $text '$key' is missing from $file"
				);
			}
		}
	}

	/**
	 * Get a different branch types
	 *
	 * @param string $dir
	 */
	protected function setBranchLists( string $dir ) :void {
		$branchLists = [];
		$configJson = $this->getConfigJson( $dir );

		if ( is_readable( $configJson ) ) {
			$branchLists = json_decode(
				file_get_contents( $configJson ),
				true
			);
		}

		$this->stupidSchemaCheck( 'key', $branchLists, $configJson );

		// This comes after we load all the default configuration
		// so it is possible to override default.conf and $branchLists
		if ( is_readable( $dir . '/local.conf' ) ) {
			require $dir . '/local.conf';
		}

		$this->stupidSchemaCheck(
			'index is null for', $branchLists, 'local.conf'
		);
		$this->branchedExtensions = $branchLists['extensions'] ?? [];
		$this->branchedSubmodules = $branchLists['submodules'] ?? [];
		$this->specialExtensions = $branchLists['special_extensions'] ?? [];
	}

	/**
	 * Check that everything is up to date with origin
	 *
	 * @param string $dir
	 * @param string $branch
	 */
	public function check( string $dir, string $branch = "master" ) :void {
		$changes = $this->control->getChanges();
		if ( $changes ) {
			$this->logger->notice(
				"You have local changes in your tools/release checkout:\n"
				. $changes
			);
		}
	}

	/**
	 * Handle brancher initialization
	 */
	public function initialize() :void {
		// Best way to get the full path to the file being executed.
		[ $arg0 ] = get_included_files();
		$dir = dirname( $arg0 );

		// Warn if we have any outstanding changes.
		$this->check( $dir, "master" );
		$this->setDefaults( $dir );
		$this->setBranchLists( $dir );
	}

	/**
	 * setup an alreadyBranched array that has the names of all extensions
	 * up-to the extension from which we would like to start branching
	 *
	 * @param string|null $extName - name of extension from which to
	 * start branching
	 */
	public function setStartExtension( string $extName = null ) :void {
		if ( $extName === null ) {
			return;
		}

		$foundKey = false;
		foreach ( [ $this->branchedExtensions ] as $branchedArr ) {
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
				"Could not find extension '{$extName}' in any branched "
				. "Extension list"
			);
		}

		// Should make searching array easier
		$this->alreadyBranched = array_flip( $this->alreadyBranched );
	}

	/**
	 * Print an error and die
	 *
	 * @param string $msg
	 * @return never-returns
	 */
	public function croak( string $msg ) :void {
		$this->logger->error( $msg );
		exit( 1 );
	}

	/**
	 * For a list of repositories, return a list of all those that do
	 * not have a $this->newVersion branch yet with the current HEAD
	 * of the master branch.
	 *
	 * @param array $repos list of repositories
	 * @return array
	 */
	protected function queryBranchPoints( array $repos ) :array {
		return $this->control->getBranchInfo( $this->getMappedRepos( $repos ) );
	}

	/**
	 * Map the list of repositories' short names to their longer onex.
	 *
	 * @param array $repos list of short names
	 * @return array
	 */
	protected function getMappedRepos( array $repos ) {
		return array_map(
			function ( $repo ) {
				return $this->qualifyRepo( $repo );
			}, $repos
		);
	}

	/**
	 * Does this string start with that one?
	 *
	 * @param string $thisStr
	 * @param string $thatStr
	 * @return bool
	 */
	protected function startsWith( string $thisStr, string $thatStr ) :bool {
		$len = mb_strlen( $thatStr, 'utf-8' );
		return mb_substr( $thisStr, 0, $len, 'utf-8' ) === $thatStr;
	}

	/**
	 * Translate this repository name to what it is in gerrit.
	 *
	 * @param string $repo
	 * @return string
	 */
	protected function qualifyRepo( string $repo ) :string {
		if (
			$this->startsWith( $repo, "extensions/" ) ||
			$this->startsWith( $repo, "skins/" ) ||
			$this->startsWith( $repo, "vendor" )
		) {
			return "mediawiki/" . $repo;
		}
		return $repo;
	}

	/**
	 * Branch and add a group of extensions as submodules
	 *
	 * @param array $extension
	 */
	public function branchAndAddGroup( array $extension ) :void {
		$map = [];
		foreach ( $extension as $ext ) {
			$map[$ext] = $this->qualifyRepo( $ext );
		}
		foreach ( $map as $dir => $repo ) {
			if ( !$this->control->hasBranch( $repo, $this->newVersion ) ) {
				$this->branchRepo( $repo );
			}
			if ( !$this->control->hasSubmodule(
					 self::MWREPO, $repo, $dir
			) ) {
				$this->control->addSubmodule( self::MWREPO, $repo, $dir );
			} else {
				$this->control->checkoutSubmodule( self::MWREPO, $repo, $dir );
			}
		}
	}

	/**
	 * Entry point to branching
	 */
	public function execute() :void {
		$branchPoints = [];

		if ( !$this->control->hasBranch( self::MWREPO, $this->newVersion ) ) {
			$this->branchRepo( self::MWREPO );
		}

		$this->control->ensureEmptyDir( $this->getWorkDir() );
		$this->control->clone(
			self::MWREPO, $this->newVersion, $this->getWorkDir()
		);
		$this->branchAndAddGroup( $this->branchedExtensions );
		$this->branchAndAddGroup( $this->specialExtensions );
	}

	/**
	 * Create this branch
	 *
	 * @param string $branchName
	 * @param string $from branch point
	 */
	public function createBranch( string $branchName, string $from ) :void {
		$this->control->createBranch( 'origin', $branchName, $from );
	}

	/**
	 * Entry point to branch
	 *
	 * @param string $repo where the git checkout is
	 * @param string $branch
	 */
	public function branchRepo(
		string $repo,
		string $branch = 'master'
	) :void {
		$this->logger->notice( "Creating {$this->newVersion} branch for $repo" );
		$this->control->createBranch( $repo, $branch, $this->newVersion );
	}

	/**
	 * Create (if necessary) the new branch
	 *
	 * @param string $repo to create it for
	 */
	public function create( string $repo ) :void {
		$hasBranch = $this->control->hasBranch( $repo, $this->newVersion );
		if ( !$hasBranch ) {
			$this->logger->notice(
				"Creating {$this->newVersion} for {$this->clonePath}."
			);
			$this->control->checkout( $this->newVersion );
		}
	}

	/**
	 * Take care of updating the version variagble
	 */
	public function handleVersionUpdate() :void {
		# Fix MW_VERSION
		if ( $this->fixVersion( "includes/Defines.php" ) ) {
			# Do intermediate commit
			$ret = $this->control->runCmd(
				'git', 'commit', '-a', '-m',
				"Creating new " . $this->getShortname()
				. " {$this->newVersion} branch"
			);
			if ( $ret !== 0 ) {
				$this->croak( "Intermediate commit failed!" );
			}
		} else {
			$this->logger->notice(
				'Version update already applied, but continuing anyway'
			);
		}
	}

	/**
	 * Take care of any other git checkouts
	 */
	public function handleSubmodules() :void {
		# Add extensions/skins/vendor
		foreach ( $this->branchedExtensions as $name ) {
			$this->control->addSubmodule(
				$this->newVersion, "{$this->repoPath}/{$name}", $name
			);
		}

		# Add extension submodules
		foreach ( array_keys( $this->specialExtensions ) as $name ) {
			$ret = $this->control->runCmd(
				'git', 'submodule', 'add', '-f', '-b', $this->newVersion,
				"{$this->repoPath}/{$name}", $name
			);
			if ( $ret !== 0 ) {
				$this->croak( "Adding submodule ($name) failed!" );
			}
		}
	}

	/**
	 * Push the branch
	 *
	 * @param string $branchName
	 */
	public function branch( string $branchName ) :void {
		# Clone the repository
		$oldVersion = $this->oldVersion === $branchName
					? $branchName
					: $this->branchPrefix . $this->oldVersion;

		$this->create( self::MWREPO );
		$this->handleSubmodules();
		$this->handleVersionUpdate();
		$this->publish();
	}

	/**
	 * Push the branch to gerrit.
	 */
	public function publish() :void {
		$this->control->push( self::MWREPO );
	}

	/**
	 * Fix the version number (MW_VERSION) in the given file.
	 *
	 * @param string $fileName
	 * @return bool
	 */
	public function fixVersion( string $fileName ) :bool {
		$ret = false;
		$before = file_get_contents( $fileName );
		if ( $before === false ) {
			$this->croak( "Error reading $fileName" );
		}

		$after = preg_replace(
			'/^( define\( \s+ \'MW_VERSION\', \s+  \' ) [^;\']* ( \' \s+ \); \s* ) $/xm',
			"\\1'{$this->newVersion}'\\2", $before, -1, $count
		);
		if ( $before !== $after ) {
			$ret = file_put_contents( $fileName, $after );
			if ( $ret === false ) {
				$this->croak( "Error writing $fileName" );
			}
			$this->logger->notice(
				"Replaced $count instance of MW_VERSION in $fileName"
			);
		}

		if ( $count === 0 ) {
			$this->croak( "Could not find MW_VERSION in $fileName" );
		}
		return !( $ret === false );
	}
}
