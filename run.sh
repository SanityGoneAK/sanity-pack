poetry install
git submodule update --init --recursive
poetry run python -m sanity_pack
git config --global user.name "Sanity;Gone"
git config --global user.email "actions@users.noreply.github.com"
git pull --all
git add cache
git add sanity_pack/fbs
git diff-index --quiet HEAD || git commit -m "Update: Data updates" && git push