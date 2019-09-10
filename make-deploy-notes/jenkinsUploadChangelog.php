<?php
/**
 * Copyright © 2013 Sam Reed
 * Copyright © 2019 Tyler Cipriani, Mukunda Modell
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
 */

if ( count( $argv ) !== 3 ) {
	print "usage: $argv[0] 1.31.0-wmf.11 notes-file\n";
	exit( 1 );
}

$version = $argv[1];
$notesFile = $argv[2];

# environment variables available as $_SERVER vars in docker env
$mwUser = $_SERVER['MEDIAWIKI_USR'];
$mwPass = $_SERVER['MEDIAWIKI_PSW'];

$output = file_get_contents( $notesFile );

require_once __DIR__ . '/botclasses.php';
$wiki = new wikipedia( 'https://www.mediawiki.org/w/api.php' );
$wiki->login( $mwUser, $mwPass );

list( $major, $minor ) = getMajorMinor( $version );
$wiki->edit( "MediaWiki 1.{$major}/wmf.{$minor}/Changelog",
	$output, "Update changelog for $version", false, false );

print "Changelog updated\n";

/**
 * @param string $input A raw version string.
 * @return array|null
 */
function getMajorMinor( $input ) {
	$matches = array();
	// match any version like 1.26wmf22 or the new semver 1.27.0-wmf1
	if ( preg_match( "/1\.(\d{2})\.0\-wmf\.(\d{1,2})/", $input, $matches ) ) {
		// var_dump( $matches );
		$major = intval( $matches[1] );
		$minor = intval( $matches[2] );
		return array( $major, $minor );
	}
	return null;
}
