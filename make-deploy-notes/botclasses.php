<?php
/**
 * botclasses.php - Bot class for interacting with MediaWiki.
 *
 *  Copyright Cobi
 *  Copyright 2008-2012 Chris G <http://en.wikipedia.org/wiki/User:Chris_G>
 *  Copyright 2021 Krinkle
 *
 *  This program is free software; you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation; either version 2 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program; if not, write to the Free Software
 *  Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
 */

class MediaWikiApi {
	public $url;
	private $cookiefile;

	public function __construct( $url = 'https://test.wikipedia.org/w/api.php' ) {
		$this->url = $url;
		$this->cookiefile = tempnam( sys_get_temp_dir(), 'mwcookiejar' );
	}

	private function httpInit() {
		$ch = curl_init();
		// Let cURL reuse the cookie jar between requests
		curl_setopt( $ch, CURLOPT_COOKIEJAR, $this->cookiefile );
		curl_setopt( $ch, CURLOPT_COOKIEFILE, $this->cookiefile );
		curl_setopt( $ch, CURLOPT_USERAGENT, 'Bot (mediawiki-tools-release/make-deploy-notes)' );
		curl_setopt( $ch, CURLOPT_RETURNTRANSFER, true );
		curl_setopt( $ch, CURLOPT_TIMEOUT, 30 );
		curl_setopt( $ch, CURLOPT_CONNECTTIMEOUT, 10 );
		return $ch;
	}

	public function httpPost( $url, $data ) {
		$time = microtime( true );
		$ch = $this->httpInit();
		curl_setopt( $ch, CURLOPT_URL, $url );
		curl_setopt( $ch, CURLOPT_POST, 1 );
		curl_setopt( $ch, CURLOPT_POSTFIELDS, $data );
		$resp = curl_exec( $ch );
		echo '# POST ' . $url
			. ' (' . round( microtime( true ) - $time, 1 ) . 's; '
			. number_format( strlen( $resp ) ) . "B)\n";
		return $resp;
	}

	public function httpGet( $url ) {
		$time = microtime( true );
		$ch = $this->httpInit();
		curl_setopt( $ch, CURLOPT_URL, $url );
		curl_setopt( $ch, CURLOPT_HEADER, 0 );
		$resp = curl_exec( $ch );
		echo '# GET ' . $url
			. ' (' . round( microtime( true ) - $time, 1 ) . 's; '
			. number_format( strlen( $resp ) ) . "B)\n";
		return $resp;
	}

	public function query( string $query, array $post = null ): array {
		if ( $post === null ) {
			$resp = $this->httpGet( $this->url . '?format=json&' . $query );
		} else {
			$resp = $this->httpPost( $this->url . '?format=json&' . $query, $post );
		}
		$result = $resp ? json_decode( $resp, true ) : false;
		if ( !$result || isset( $result['error'] ) ) {
			throw new Exception( "API error" );
		}
		return $result;
	}

	public function login( string $user, string $pass ): array {
		$post = [ 'lgname' => $user, 'lgpassword' => $pass ];
		$ret = $this->query( 'action=login', $post );
		// Required per https://bugzilla.wikimedia.org/show_bug.cgi?id=23076
		if ( $ret['login']['result'] === 'NeedToken' ) {
			$post['lgtoken'] = $ret['login']['token'];
			$ret = $this->query( 'action=login', $post );
		}
		if ( $ret['login']['result'] !== 'Success' ) {
			print_r( $ret );
			throw new Exception( "Login error" );
		}
		return $ret;
	}

	public function getedittoken(): string {
		$ret = $this->query( 'action=query&meta=tokens&type=csrf' );
		return $ret['query']['tokens']['csrftoken'];
	}

	public function __destruct() {
		// phpcs:ignore Generic.PHP.NoSilencedErrors.Discouraged
		@unlink( $this->cookiefile );
	}
}
