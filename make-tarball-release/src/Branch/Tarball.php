<?php

/*
 * Copyright (C) 2019  Wikimedia Foundation, Inc.
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * @author Mark A. Hershberger <mah@nichework.com>
 */

namespace Wikimedia\Release\Branch;

use Wikimedia\AtEase\AtEase;
use Wikimedia\Release\Branch;

class Tarball extends Branch {

	/**
	 * @inheritDoc
	 */
	public static function getShortname(): string {
		return 'tarball';
	}

	/**
	 * @inheritDoc
	 */
	public static function getDescription(): string {
		return 'Prepare the tree for a tarball release';
	}

	/**
	 * @inheritDoc
	 */
	public function getWorkDir(): string {
		$dir = getenv( "mwDir" );
		if ( !$dir ) {
			$dir = sys_get_temp_dir() . '/make-tarball-branch';
		}
		return $dir;
	}

	/**
	 * @inheritDoc
	 */
	protected function getBranchPrefix(): string {
		return "";
	}

	/**
	 * @inheritDoc
	 */
	public function getRepoPath(): string {
		$path = getenv( "gerritHead" );
		if ( !$path ) {
			$path = 'https://gerrit.wikimedia.org/r';
		}
		return "$path/mediawiki";
	}

	/**
	 * @inheritDoc
	 */
	protected function getBranchDir(): string {
		$branch = getenv( "relBranch" );
		if ( $branch === false ) {
			// Psalm complains if we let $branch remain false since
			// that doesn't match our return type.
			$branch = "";
			$this->croak( "The environment variable relBranch must be set" );
		}
		return $branch;
	}

	/**
	 * @inheritDoc
	 */
	protected function getConfigJson( string $dir ): string {
		return $dir . '/tarball-config.json';
	}

	public function setupBuildDirectory(): string {
		if ( !is_dir( $this->buildDir ) ) {
			AtEase::suppressWarnings();
			if ( lstat( $this->buildDir ) !== false ) {
				$this->croak(
					"Unable to create build directory {$this->buildDir} because file exists"
				);
			}
			AtEase::restoreWarnings();
			if ( !mkdir( $this->buildDir ) ) {
				$this->croak(
					"Unable to create build directory {$this->buildDir}"
				);
			}
		}
		return $this->buildDir;
	}

}
