<?php

$wgDBserver = 'db';
$wgDBuser = 'wikiuser';
$wgDBpassword = 'password';

/**
 * @see wmf-config/filebackend.php
 */
$wmfSwiftConfig = [];
$wmfSwiftConfig['dev'] =
$wmfSwiftConfig['eqiad'] =
$wmfSwiftConfig['codfw'] = [
		'cirrusAuthUrl' => null,
		'cirrusUser' => null,
		'cirrusKey' => null,
		'thumborUser' => null,
		'thumborPrivateUser' => null,
		'thumborUrl' => null,
		'thumborSecret' => null,
		'user' => null,
		'key' => null,
		'tempUrlKey' => null,
];

$wmgCaptchaSecret = '*';
$wmgCaptchaPassword = '*';

$wmgLogstashPassword = '*';

$wmgRedisPassword = '*';

$wmgTranslationNotificationUserPassword = '*';

$wmgVERPsecret = '*';

$wmgElectronSecret = null;

$wmgContentTranslationCXServerAuthKey = null;
$wmgSessionStoreHMACKey = null;
