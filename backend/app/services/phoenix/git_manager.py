
import os
from typing import List, Optional
from loguru import logger
from git import Repo, Actor
from app.core.config import settings

class GitManager:
    """
    Git 仓库管理器 (Git Manager)
    
    负责代码和测试用例的版本控制:
    1. 初始化/加载仓库
    2. 提交文件 (Auto-Commit)
    3. 推送变更 (Push)
    """
    
    def __init__(self, repo_path: Optional[str] = None):
        self.repo_path = repo_path or settings.GIT_REPO_PATH
        self.repo: Optional[Repo] = None
        self._init_repo()

    def _init_repo(self):
        """初始化或加载 Git 仓库"""
        if not os.path.exists(self.repo_path):
            os.makedirs(self.repo_path, exist_ok=True)
            self.repo = Repo.init(self.repo_path)
            logger.info(f"Initialized new Git repo at {self.repo_path}")
        else:
            try:
                self.repo = Repo(self.repo_path)
                logger.info(f"Loaded existing Git repo at {self.repo_path}")
            except Exception:
                # 可能是个空文件夹但没 .git
                self.repo = Repo.init(self.repo_path)
                logger.info(f"Re-initialized Git repo at {self.repo_path}")

        # Configure User
        with self.repo.config_writer() as git_config:
            git_config.set_value("user", "name", settings.GIT_USER_NAME)
            git_config.set_value("user", "email", settings.GIT_USER_EMAIL)

    def commit_file(self, file_path: str, message: str) -> str:
        """
        提交指定文件
        
        Args:
            file_path: 相对路径 (相对于 repo root) 或 绝对路径
            message: 提交信息
            
        Returns:
            commit_hexsha: 提交的哈希值
        """
        if not self.repo:
            raise RuntimeError("Git Repo not initialized")
            
        try:
            # Add file
            self.repo.index.add([file_path])
            
            # Commit
            actor = Actor(settings.GIT_USER_NAME, settings.GIT_USER_EMAIL)
            commit = self.repo.index.commit(message, author=actor, committer=actor)
            
            logger.info(f"Git Commit [{commit.hexsha[:7]}]: {message}")
            return commit.hexsha
            
        except Exception as e:
            logger.error(f"Git Commit Failed: {e}")
            raise

    def push_changes(self, remote_name: str = "origin", branch: str = "main"):
        """推送变更到远程"""
        if not self.repo:
            return
            
        try:
            remote = self.repo.remote(name=remote_name)
            remote.push(refspec=f"{branch}:{branch}")
            logger.info(f"Git Push to {remote_name}/{branch} success.")
        except ValueError:
            logger.warning(f"Remote '{remote_name}' not found. Skip push.")
        except Exception as e:
            logger.error(f"Git Push Failed: {e}")

    def get_history(self, max_count: int = 10) -> List[dict]:
        """获取提交历史"""
        if not self.repo:
            return []
            
        commits = []
        try:
            for commit in self.repo.iter_commits(max_count=max_count):
                commits.append({
                    "hash": commit.hexsha,
                    "message": commit.message.strip(),
                    "author": commit.author.name,
                    "date": commit.committed_datetime.isoformat()
                })
        except Exception:
            pass # No commits yet
            
        return commits
