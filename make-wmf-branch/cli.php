<?php
if ( php_sapi_name() !== 'cli' ) {
	echo "This script only works in CLI mode\n";
	exit( 1 );
}
