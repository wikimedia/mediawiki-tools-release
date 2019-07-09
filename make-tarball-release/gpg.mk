#-*-tab-width: 4; fill-column: 76; whitespace-line-column: 77 -*-
# vi:shiftwidth=4 tabstop=4 textwidth=76

# Copyright (C) 2019  Wikimedia Foundation, Inc.

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

keyUrl=https://www.mediawiki.org/keys/keys.html
GNUPGHOME=${workDir}/gpg
export GNUPGHOME
myGpg=$(shell HOME=${oldHOME} gpgconf --list-dirs |							\
		awk -F: '$$1 == "homedir" {print $$2}')

# Continue without signature after downloading
#
noSigOk ?= false
export noSigOk
doNotFail=$(if $(filter-out true,${noSigOk}),true,false)

# Sign the release
doSign ?= true
export doSign

signTagIfSigning=$(if $(filter-out false,${doSign}),-s,-a)

# KeyID to use
keyId ?= $(shell git config --get user.signingkey || (						\
	gpgconf --list-options gpg |											\
	awk -F: '$$1 == "default-key" {print $$10}' | sed s,^.,,) )
export keyId

GPG_TTY=$(tty)
export GPG_TTY

${gpgDir}: ${workDir}
	# Without the private-keys dir, secret keys are not (completely?) imported.
	mkdir -p ${gpgDir}/private-keys-v1.d
	test `id -u` != 0 || sudo chown -R `id -u` ${gpgDir}
	chmod -R 700 ${gpgDir}

# Fetch PGP keys from keyUrl
#
.PHONY:
fetchKeys: ${gpgDir}
	wget -q -O - ${keyUrl} | gpg --import

# Show information about the key used for signing.
showKeyInfo:
	gpg --list-key ${keyId}

# Verify a signature for a file
#
verifyFile:
	test -n "${sigFile}" -a -f ${sigFile} || (								\
		echo "The sigFile (${sigFile}) does not exist.";					\
		exit 2																\
	)
	(																		\
		verify=`gpg --batch --verify ${sigFile} 							\
											$(basename ${sigFile}) 2>&1`;	\
		echo $$verify | grep -q 'Good signature'							\
			&& gpg --batch --verify ${sigFile} $(basename ${sigFile})		\
			|| (															\
				test "${getUnknownKeys}" = "false"							\
				&& echo "Cannot verify file because we don't have the key"	\
				|| (														\
					key=`echo $$verify |									\
						sed 's,.*gpg: using [^ ]* key \([^ ]*\).*,\1,'`;	\
					gpg --recv $$key &&										\
					gpg --batch --verify ${sigFile} $(basename ${sigFile})	\
				)															\
			)																\
	)

#
verifyKeyIDSet:
	test -n "${keyId}" -o "${doSign}" = "false" || (						\
		echo ${indent}"Please specify a keyId!";							\
		echo; exit 1;														\
	)

verifySecretKeyExists: ${gpgDir} verifyKeyIDSet
	gpg --list-secret-keys ${keyId} > /dev/null 2>&1 || (					\
		echo ${indent}"No secret key matching '${keyId}' in the keyring at";\
		echo ${indent} ${gpgDir}.; echo;									\
		${MAKE} checkForSecretKeyInMainKeyring keyId=${keyId}				\
		echo; exit 1														\
	)

checkForSecretKeyInMainKeyring: verifyKeyIDSet
	gpg --homedir=${myGpg} --list-secret-keys ${keyId} > /dev/null 2>&1 && (\
		echo ${indent}"Secret key exists in ${myGpg}!";						\
		echo ${indent}"Use 'make copySecretKey' to copy it."; echo			\
	) || (																	\
		echo ${indent}"No secret key matching '${keyId}' in the keyring at";\
		echo ${indent}${myGpg}.												\
	)

# Copy an un-password-protected secret key to the work dir
#
copySecretKey: ${gpgDir} verifyKeyIDSet
	(																		\
		gpg --homedir=${myGpg} --export-secret-key ${keyId};				\
		gpg --homedir=${myGpg} --export ${keyId};							\
	) | gpg --batch --import

