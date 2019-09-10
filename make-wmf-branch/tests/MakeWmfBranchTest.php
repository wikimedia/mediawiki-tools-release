<?php
require_once __DIR__ . '/../MakeWmfBranch.php';

/**
 * @covers MakeWmfBranch
 */
class MakeWmfBranchTest extends \PHPUnit\Framework\TestCase {

	/**
	 * Very basic test to guard us from typos in the repository names.
	 *
	 * @dataProvider provideConfiguredRepos
	 */
	public function testFoo( $repo ) {
		$this->assertRegExp( '%^(extensions/|skins/|vendor$)%', $repo );
	}

	public static function provideConfiguredRepos() {
		$makewmfbranch = new MakeWmfBranch( '1.99', '2.0' );

		$repos = array_merge(
			$makewmfbranch->branchedExtensions,
			array_keys( $makewmfbranch->branchedSubmodules ),
			array_keys( $makewmfbranch->specialExtensions )
		);

		$testcases = [];
		foreach ( $repos as $repo ) {
			$testcases[] = [ $repo ];
		}
		return $testcases;
	}

}
