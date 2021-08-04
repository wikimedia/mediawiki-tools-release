<?php
require_once __DIR__ . '/botclasses.php';
$wiki = new MediaWikiApi( 'https://www.mediawiki.org/w/api.php' );

$i = 0;
$success = true;

function test( $name, $actual, $expected ) {
	global $i;
	$i++;
	if ( $actual === $expected ) {
		echo "ok $i $name\n";
	} else {
		global $success;
		$success = false;
		echo "not ok $i $name\n  ---\n  actual: "
			. json_encode( $actual ) . "\n  expected: "
			. json_encode( $expected ) . "\n";
	}
}

echo "TAP version 13\n";

test( 'getedittoken()',
	$wiki->getedittoken(),
	'+\\'
);

test( 'query() GET',
	$wiki->query( 'action=query&meta=siteinfo' )['query']['general']['servername'],
	'www.mediawiki.org'
);

test( 'query() POST',
	$wiki->query( '', [ 'action' => 'query', 'meta' => 'siteinfo' ] )['query']['general']['servername'],
	'www.mediawiki.org'
);

echo "1..$i\n";
if ( !$success ) {
	exit( 1 );
}
