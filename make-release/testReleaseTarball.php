<?php
/**
 * MediaWiki tarball tester.
 *
 * Based on the PHPUnit Framework.
 *
 * Usage:
 *   phpunit [switches] testReleaseTarball.php <version>
 *
 * Example:
 *   phpunit --log-junit results.xml testReleaseTarball.php 1.21.2
 *
 * @author Markus Glaser
 * @file
 */

/**
 * PHPUnit based tests.
 */
class ReleaseTarballTestCase extends \PHPUnit\Framework\TestCase {

	/** Version we will test out */
	protected static $version;

	/** Filename of the tarball for the version */
	protected static $tarball;

	/** Path where the tarball got extracted to */
	protected static $basePath;

	/**
	 * Helper to easily set the target version AND the tarball name
	 */
	protected static function setTargetVersion( $version ) {
		self::$version = $version;
		self::$tarball = "build/mediawiki-{$version}.tar.gz";
		self::$basePath = "mediawiki-{$version}";
	}

	public static function setUpBeforeClass() {
		parent::setUpBeforeClass();
		// version tag is the last argument
		self::setTargetVersion( array_pop( $_SERVER['argv'] ) );
	}

	public static function tearDownAfterClass() {
		# remove install dir
		if ( file_exists( self::$basePath ) && is_dir( self::$basePath ) ) {
			# There seems to be a handle on the language files immediately after
			# install, so lets wait a bit
			sleep( 1 );

			$cmd = 'rm -r ' . escapeshellarg( self::$basePath );
			exec( $cmd );
		}

		parent::tearDownAfterClass();
	}

	/**
	 * Make sure the version passed to us is valid
	 */
	public function testTargetVersionIsValid() {
		$this->assertRegExp( '/\d\.\d+\.\d+.*/',
			self::$version,
			"Must be passed a valid MediaWiki version"
		);
	}

	public function testHaveATarballForTargetVersion() {
		$this->assertFileExists( self::$tarball,
			self::$tarball . " could not be find. Please run: make-release.py " . self::$version
		);
	}

	public function testExtractTarball() {
		// extract tarball as described in http://www.mediawiki.org/wiki/Manual:Installing_MediaWiki
		$cmd = 'tar xzf ' . escapeshellarg( self::$tarball );

		exec( $cmd, $output, $exitCode );
		$this->assertEquals( 0, $exitCode,
			"Shell command $cmd failed with exit code $exitCode"
		);

		# TODO: this assertion is not enough
		$this->assertFileExists( self::$basePath,
			"Tarball " . self::$tarball . "should have been extracted to "
			. self::$basePath
		);

		$this->assertFileExists( self::$basePath . '/includes/DefaultSettings.php',
			"DefaultSettings.php could not be found."
		);
	}

	public function testWgversionMatchTargetedVersion() {
		$file = file_get_contents( self::$basePath . '/includes/DefaultSettings.php' );
		preg_match( '/\$wgVersion\s+=\s+\'(.*)\';/',
			$file, $matches
		);
		$this->assertEquals( self::$version,
			$matches[1],
			"\$wgVersion is not set correctly."
		);
	}

	public function testCliInstaller() {
		$cmd = 'php ' . escapeshellarg( self::$basePath ) . '/maintenance/install.php'
				// SQLite for installation
				.' --dbtype=sqlite'
				// Put SQLite file in MW install path
				.' --dbpath=' . escapeshellarg( self::$basePath )
				// Put required DB name in
				.' --dbname=tmp'
				// admin pass
				.' --pass=releaseTest'
				// name
				.' TarballTestInstallation'
				// admin
				.' WikiSysop';

		exec( $cmd, $output, $exitCode );
		$this->assertEquals( 0, $exitCode,
			"Shell command $cmd failed with exit code $exitCode"
		);
		$this->assertFileExists( self::$basePath . '/LocalSettings.php',
			"Installation failed: LocalSettings.php could not be found."
		);
	}

}
