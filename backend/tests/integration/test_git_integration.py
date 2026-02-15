
import pytest
import os
import shutil
from git import Repo
from app.services.phoenix.git_manager import GitManager

@pytest.fixture
def temp_git_repo(tmp_path):
    repo_dir = tmp_path / "test_repo"
    yield str(repo_dir)
    # Cleanup done by tmp_path fixture

def test_git_workflow(temp_git_repo):
    # 1. Initialize
    git_manager = GitManager(repo_path=temp_git_repo)
    assert os.path.exists(os.path.join(temp_git_repo, ".git"))
    
    # 2. Create File
    file_name = "test_file.txt"
    file_path = os.path.join(temp_git_repo, file_name)
    with open(file_path, "w") as f:
        f.write("Hello Git")
        
    # 3. Commit
    commit_hash = git_manager.commit_file(file_name, "Initial Commit")
    assert commit_hash is not None
    assert len(commit_hash) == 40
    
    # 4. Verify History
    history = git_manager.get_history()
    assert len(history) == 1
    assert history[0]["message"] == "Initial Commit"
    assert history[0]["hash"] == commit_hash

def test_git_push_mock(temp_git_repo):
    # Just verify it doesn't crash on push (since we have no remote)
    git_manager = GitManager(repo_path=temp_git_repo)
    
    # Create a dummy file and commit to have something on branch
    file_path = os.path.join(temp_git_repo, "dummy.txt")
    with open(file_path, "w") as f: f.write("dummy")
    git_manager.commit_file("dummy.txt", "dummy commit")
    
    # Push (should log warning but not fail)
    git_manager.push_changes(remote_name="params_origin")
