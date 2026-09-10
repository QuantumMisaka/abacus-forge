# Native ABACUS MD fixture

The `running_md.log` rows follow ABACUS's native
`Energy (Ry) / Potential (Ry) / Kinetic (Ry) / Temperature (K)` block,
with the optional pressure column. `MD_dump` contains the native frame marker
shape. Values are compact synthetic facts based on the ABACUS output format;
they are not a scientific validation case.

Format references: `abacus-develop` revision `94576a801` (`source/source_md`
and `source/source_esolver`) and the repository-local `abacus-test` fixture
revision `1c9acbca026234ba91cdc19bca2f989d19d2ccff`. Both split and historical
unitless/merged MD header shapes are covered by the collection regressions.
