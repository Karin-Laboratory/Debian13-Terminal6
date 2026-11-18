#!/bin/sh
set -eu

# Stage/install a previously built prplMesh prefix and its external ACL policy.
# This never enables or starts the service.
if [ "$#" -ne 3 ]; then
	echo "usage: $0 <prplmesh-cmake-install-prefix> <prplmesh-acl-policy-json> <expected-elf-machine>" >&2
    exit 2
fi
src=$1
acl_policy=$2
expected_machine=$3
dest=${DESTDIR:-}
if [ ! -d "$src" ]; then
    echo "build prefix does not exist: $src" >&2
    exit 1
fi
for binary in ieee1905_transport beerocks_controller beerocks_agent beerocks_vendor_message; do
    if [ ! -x "$src/bin/$binary" ]; then
        echo "missing built binary: $binary" >&2
        exit 1
    fi
done
if ! command -v readelf >/dev/null 2>&1; then
	echo "readelf is required to verify target architecture" >&2
	exit 1
fi
for binary in ieee1905_transport beerocks_controller beerocks_agent beerocks_vendor_message; do
	actual_machine=$(readelf -h "$src/bin/$binary" | awk -F: '/Machine:/{sub(/^[[:space:]]+/, "", $2); print $2}')
	if [ "$actual_machine" != "$expected_machine" ]; then
		echo "wrong ELF machine for $binary: $actual_machine (expected $expected_machine)" >&2
		exit 1
	fi
done
if [ -d "$src/lib" ]; then
	while IFS= read -r library; do
		actual_machine=$(readelf -h "$library" | awk -F: '/Machine:/{sub(/^[[:space:]]+/, "", $2); print $2}')
		if [ "$actual_machine" != "$expected_machine" ]; then
			echo "wrong ELF machine for runtime library $(basename "$library"): $actual_machine (expected $expected_machine)" >&2
			exit 1
		fi
	done <<EOF
$(find "$src/lib" -type f -name '*.so*' -print)
EOF
fi
if [ ! -f "$acl_policy" ] || [ -L "$acl_policy" ]; then
    echo "missing or unsafe prplMesh ACL policy: $acl_policy" >&2
    exit 1
fi

install -d -m 0755 "$dest/opt/terminal6-easymesh"
cp -a "$src/." "$dest/opt/terminal6-easymesh/"
# prplMesh installs its ACL policy outside CMAKE_INSTALL_PREFIX; preserve it.
install -d -m 0755 "$dest/etc/acl/admin"
install -m 0644 "$acl_policy" "$dest/etc/acl/admin/prplmesh.json"
install -d -m 0755 "$dest/usr/libexec"
install -m 0755 "$(dirname "$0")/terminal6-easymesh-preflight.py" \
    "$dest/usr/libexec/terminal6-easymesh-preflight"
install -m 0755 "$(dirname "$0")/terminal6-easymesh-supervisor.py" \
    "$dest/usr/libexec/terminal6-easymesh-supervisor"
install -m 0755 "$(dirname "$0")/render-platform-db.py" \
    "$dest/usr/libexec/terminal6-easymesh-render-platform-db"
install -d -m 0755 "$dest/etc/systemd/system"
install -m 0644 "$(dirname "$0")/terminal6-prplmesh.service" \
    "$dest/etc/systemd/system/terminal6-prplmesh.service"
install -d -m 0755 "$dest/etc/terminal6-easymesh"
install -m 0644 "$(dirname "$0")/node.conf.example" \
    "$dest/etc/terminal6-easymesh/node.conf.example"
install -m 0644 "$(dirname "$0")/prplmesh_platform_db.example" \
    "$dest/etc/terminal6-easymesh/prplmesh_platform_db.example"
install -d -m 0755 "$dest/usr/share/doc/terminal6-easymesh"
install -m 0644 "$(dirname "$0")/../../docs/easymesh/STATUS-20261115.ja.md" \
    "$dest/usr/share/doc/terminal6-easymesh/STATUS-20261115.ja.md"
echo "Installed files only. Configure private files and create enabled marker to opt in."
