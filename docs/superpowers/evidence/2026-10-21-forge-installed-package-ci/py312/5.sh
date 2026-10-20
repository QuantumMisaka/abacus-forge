wheels=(dist/*.whl)
test "${#wheels[@]}" -eq 1
python -m pip install "${wheels[0]}[dev,abacuslite]"
python -m pip check
echo "ABACUS_FORGE_WHEEL=$PWD/${wheels[0]}" >> "$GITHUB_ENV"
