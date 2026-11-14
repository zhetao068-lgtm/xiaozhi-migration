# 小智项目迁移

在新电脑装好 Git 和 Git LFS 后直接克隆。仓库公开，克隆无须登录 GitHub。

```powershell
git lfs install
git clone https://github.com/zhetao068-lgtm/xiaozhi-migration.git
```

打开 [新电脑继续使用](00-新电脑继续使用.txt) 或 [小智最终方案](小智/最终方案.md)。克隆包含完整项目、原始 3MF、两份恢复的试装草稿、过程资料及工具。约 1.39 GB。四项大文件由 Git LFS 下载。SHA256SUMS.txt 用于核对 173 个迁移文件的原始字节。

要补下载大文件，在克隆目录中执行 `git lfs pull`。
