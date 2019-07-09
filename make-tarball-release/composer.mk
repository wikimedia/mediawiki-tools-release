#-*-tab-width: 4; fill-column: 76; whitespace-line-column: 77 -*-
# vi:shiftwidth=4 tabstop=4 textwidth=76
composerInstallerSigUrl=https://composer.github.io/installer.sig
composerInstallerUrl=https://getcomposer.org/installer

# Download and verify composer binary
#
composer: composer-setup.php
	test -f $@ || (															\
		${php} composer-setup.php ${composerQuiet};							\
		mv composer.phar composer											\
	)

#
expected:
	test -f $@ ||															\
		${WGET} -O expected ${composerInstallerSigUrl}

installer:
	test -f $@ ||															\
		${WGET} -O installer ${composerInstallerUrl}

composer-setup.php: installer expected
	test -f $@ || (															\
		echo ${indent}Getting $@;											\
		echo `cat expected` installer | sha384sum -c -;						\
		mv installer composer-setup.php;									\
		rm -f expected installer											\
	)
