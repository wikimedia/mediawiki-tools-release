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

if ( count( $argv ) !== 2 ) {
	print "usage: $argv[0] wmf/1.23wmf1\n";
	exit(1);
}

$version = $argv[1];
$previousVersion = getPreviousVersion( $version );

if ( $previousVersion === null ) {
	print "usage: $argv[0] wmf/1.23wmf1\n";
	exit(1);
}

$escVer = escapeshellarg( $version );
$escPrevVer = escapeshellarg( $previousVersion );

$output = shell_exec( "php -f ./make-deploy-notes {$escPrevVer} {$escVer}" );

if ( stripos( $output, "array\n(" ) !== false ) {
	// Broken output, don't upload
	print "Output looks erroneous\n";
	return;
}

require_once( 'botclasses.php' );
$wiki = new wikipedia( 'https://www.mediawiki.org/w/api.php' );

$wiki->login( '', '' );

list( $major, $minor ) = getMajorMinor( $version );
$wiki->edit( "MediaWiki 1.{$major}/wmf{$minor}/Changelog", $output, "Update changelog for $version", false, false );

print "Changelog updated\n";

/**
 * @param $input string
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
		$minor = 22;
	} else {
		$minor--;
	}
	return "wmf/1.{$major}wmf{$minor}";
}

/**
 * @param $input string
 * @return array|null
 */
function getMajorMinor( $input ) {
	$matches = array();
	if ( preg_match( "/^wmf\/1\.(\d{2})wmf(\d{1,2})/", $input, $matches ) ) {
		// var_dump( $matches );
		$major = intval( $matches[1] );
		$minor = intval( $matches[2] );
		return array( $major, $minor );
	}
	return null;
}
