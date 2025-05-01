poetry install
git submodule update --init --recursive
poetry run python -m sanity_pack
git config user.name "Sanity;Gone"
git pull --all
git add cache
git add sanity_pack/fbs
git diff-index --quiet HEAD || git commit -m "Update: Data updates" && git push