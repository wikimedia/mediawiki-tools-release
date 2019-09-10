<?php

/**
 * @covers LintJson
 */
class LintJsonTest extends \PHPUnit\Framework\TestCase {
	/**
	 * Test that config.json is a valid JSON file
	 */
	public function testLint() {
		$path = dirname( __DIR__ ) . '/config.json';
		$content = json_decode( file_get_contents( $path ) );
		$this->assertInternalType( 'object', $content );
	}
}
