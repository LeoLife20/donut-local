#!/bin/sh
set -eu
cd "$(dirname "$0")"
xcrun clang -dynamiclib -arch arm64 -mmacosx-version-min=12.0 -fblocks -Wall -Wextra -Werror -O2 \
 -framework CoreText -framework CoreFoundation -framework CoreGraphics \
 -install_name @rpath/DonutFontPolicy.dylib font_policy.c -o DonutFontPolicy.dylib.next
mv DonutFontPolicy.dylib.next DonutFontPolicy.dylib
xcrun clang -arch arm64 -mmacosx-version-min=12.0 -Wall -Wextra -Werror -O2 \
 -framework CoreText -framework CoreFoundation -framework CoreGraphics \
 font_policy_test.c -Wl,-needed_library,"$PWD/DonutFontPolicy.dylib" -Wl,-rpath,"$PWD" -o font_policy_test
unset DONUT_FONT_POLICY
./font_policy_test > native-default.json
DONUT_FONT_POLICY=other ./font_policy_test > native-other.json
DONUT_FONT_POLICY=latin-only ./font_policy_test > native-latin-only.json
cmp native-default.json native-other.json
xcrun clang -arch arm64 -mmacosx-version-min=12.0 -Wall -Wextra -Werror -O2 \
 -framework CoreText -framework CoreFoundation -framework CoreGraphics \
 font_policy_test.c -o font_policy_test_baseline
./font_policy_test_baseline > native-unmodified.json
cmp native-unmodified.json native-default.json
xcrun clang -arch arm64 -mmacosx-version-min=12.0 -fblocks -Wall -Wextra -Werror -O2 \
 -framework CoreText -framework CoreFoundation -framework CoreGraphics \
 cmap_test.c -o cmap_test
./cmap_test > cmap-test.json
xcrun clang -arch arm64 -mmacosx-version-min=12.0 -fblocks -Wall -Wextra -Werror -O2 \
 -framework CoreText -framework CoreFoundation -framework CoreGraphics \
 uvs_test.c -o uvs_test
./uvs_test > uvs-test.json
