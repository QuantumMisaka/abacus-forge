#!/usr/bin/env bash
set -euo pipefail

# Rebuild this CPython 3.12 wheel on an equivalent Ubuntu 24.04/glibc 2.39 host.
# Usage: bash rebuild.sh /absolute/path/to/new-empty-build-directory
target_dir=${1:?provide a new absolute build directory}
if [[ ${target_dir} != /* || -e ${target_dir} ]]; then
    echo 'Build directory must be an absolute path that does not exist' >&2
    exit 2
fi

source_repo=/home/james/scratch/pyatb-sidereus-integration-20261019
pyatb_commit=5f7e1329c93b65c527151819cda7b156097e231f
eigen_commit=3147391d946bb4b6c68edd901f2add6ac1f31f8c
python312=/home/james/apps/miniforge3/envs/abacus-env/bin/python
installed_libs=/home/james/apps/miniforge3/envs/abacus-env/lib/python3.12/site-packages/pyatb.libs

[[ $(git -C "${source_repo}" rev-parse HEAD) == "${pyatb_commit}" ]]
[[ $(git -C "${source_repo}/eigen" rev-parse HEAD) == "${eigen_commit}" ]]
mkdir -p "${target_dir}/source/eigen" "${target_dir}/dist" "${target_dir}/repaired" "${target_dir}/linklib" "${target_dir}/logs"
git -C "${source_repo}" archive "${pyatb_commit}" | tar -x -C "${target_dir}/source"
git -C "${source_repo}/eigen" archive "${eigen_commit}" | tar -x -C "${target_dir}/source/eigen"

"${python312}" -m venv "${target_dir}/build-venv"
"${target_dir}/build-venv/bin/python" -m pip install \
    'build==1.6.1' 'pybind11==3.1.0' 'setuptools==84.0.0' \
    'wheel==0.48.0' 'auditwheel==6.8.2' 'patchelf==0.19.1.0'
ln -s "${installed_libs}/libopenblas-r0-f650aae0.3.3.so" "${target_dir}/linklib/libopenblas.so"
ln -s "${installed_libs}/liblapacke-7659a628.so.3.4.2" "${target_dir}/linklib/liblapacke.so"

HASH=5f7e132 LDFLAGS="-L${target_dir}/linklib" \
    "${target_dir}/build-venv/bin/python" -m build --wheel --no-isolation \
    --outdir "${target_dir}/dist" "${target_dir}/source" \
    > "${target_dir}/logs/build.log" 2>&1

PATH="${target_dir}/build-venv/bin:${PATH}" \
LD_LIBRARY_PATH="${installed_libs}" \
    "${target_dir}/build-venv/bin/auditwheel" repair \
    --plat manylinux_2_39_x86_64 --wheel-dir "${target_dir}/repaired" \
    "${target_dir}/dist/pyatb-1.1.2.dev0+5f7e132-cp312-cp312-linux_x86_64.whl" \
    > "${target_dir}/logs/auditwheel-repair.log" 2>&1
"${target_dir}/build-venv/bin/auditwheel" show "${target_dir}"/repaired/*.whl \
    > "${target_dir}/logs/auditwheel-show.log" 2>&1
sha256sum "${target_dir}"/repaired/*.whl
