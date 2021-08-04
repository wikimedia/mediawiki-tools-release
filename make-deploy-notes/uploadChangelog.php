<?php
/**
 * Copyright © 2013 Sam Reed
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
 * http://www.gnu.org/copyleft/gpl.html
 *
 * @file
 */

if ( count( $argv ) !== 2 && count( $argv ) !== 4 ) {
	print "usage: $argv[0] wmf/1.31.0-wmf.11 [username password]\n";
	exit( 1 );
}

$version = $argv[1];
$previousVersion = getPreviousVersion( $version );

if ( $previousVersion === null ) {
	print "Unable to determine prior branch, given $version as current\n";
	exit( 1 );
}

$escVer = escapeshellarg( $version );
$escPrevVer = escapeshellarg( $previousVersion );

$output = shell_exec( 'php -f ' . __DIR__ . "/make-deploy-notes {$escPrevVer} {$escVer}" );

if ( stripos( $output, "array\n(" ) !== false ) {
	// Broken output, don't upload
	print "Output looks erroneous\n";
	return;
}

require_once __DIR__ . '/botclasses.php';
$wiki = new MediaWikiApi( 'https://www.mediawiki.org/w/api.php' );

if ( isset( $argv[2] ) && isset( $argv[3] ) ) {
	$wiki->login( $argv[2], $argv[3] );
} elseif ( file_exists( __DIR__ . '/auth.php' ) ) {
	// auth.php should contain the following:
	// <?php
	// $wiki->login( 'username', 'password' );
	require_once __DIR__ . '/auth.php';
}

list( $major, $minor ) = getMajorMinor( $version );
$wiki->query( 'action=edit', [
	'title' => "MediaWiki 1.{$major}/wmf.{$minor}/Changelog",
	'text' => $output,
	'token' => $wiki->getedittoken(),
	'summary' => "Update changelog for $version",
] );

print "Changelog updated\n";

/**
 * @param string $input A raw version string.
 * @return string|null
 */
function getPreviousVersion( $input ) {
	$majorMinor = getMajorMinor( $input );
	if ( $majorMinor === null ) {
		return null;
	}
	list( $major, $minor ) = $majorMinor;
	if ( $minor === 1 ) {
		$major--;
		$minor = getPreviousMinorVersion( $major );
	} else {
		$minor--;
	}
	return "wmf/1.{$major}.0-wmf.{$minor}";
}

/**
 * Takes a major version and finds the last minor version of the previous
 * major version.
 * @param string $major The major version number (eg: '34' in '1.34.0').
 * @return string
 */
function getPreviousMinorVersion( $major ) {
	$filter = "wmf/1.{$major}.0-wmf";

	// get the list in a raw output format which would be visible in the
	// console for this command, sorted by version numbers
	$rawList = shell_exec( "git branch -a --list */{$filter}* | sort -V" );
	// convert the list (which is one string now) into an array of strings,
	// splitted at the end of each line
	$list = explode( PHP_EOL, $rawList );
	$minor = '';
	// there will be at least one (empty) line, check if there are more
	// elements, which would be the list of versions.
	if ( count( $list ) !== 1 ) {
		// remove anythign before the correct version semantic (wmf/1.26wmf1
		// or wmf/1.27.0-wmf.1) using the filter defined above
		// the array will start counting at 0 and will has one empty "line" at
		// the end, so count all elements and subtract 2
		list( $major, $minor ) = getMajorMinor( strstr( $list[ count( $list ) - 2 ], $filter ) );
	}

	// check, if there was a good result, otherwise assume, that there are 22
	// previous minor versions and use that
	return ( $minor !== "" ) ? $minor : 22;
}

/**
 * @param string $input A raw version string to extract major/minor version from.
 * @return array|null
 */
function getMajorMinor( $input ) {
	$matches = [];
	// match any version like wmf/1.26wmf22 or the new semver wmf/1.27.0-wmf1
	if ( preg_match( "/wmf\/1\.(\d{2})\.0\-wmf\.(\d{1,2})/", $input, $matches ) ) {
		// var_dump( $matches );
		$major = intval( $matches[1] );
		$minor = intval( $matches[2] );
		return [ $major, $minor ];
	}
	return null;
}
