# Streamlit Community Cloud 部署（方案一）

## 第一步：推到 GitHub

在项目目录打开终端，执行：

```bash
cd "C:\N-21AJPF46TWSF-Data\chenwang\Desktop\my cursor\BX\Simulator"

git add .
git commit -m "Deploy: Streamlit Cloud"

# 在 GitHub 网页新建空仓库（不要勾选 README），例如 bxsimulator
git remote add origin https://github.com/<你的用户名>/bxsimulator.git
git push -u origin main
```

> 建议用 **私有仓库**（Private），只有你和授权同事能看代码；应用链接仍可分享给同事使用。

## 第二步：在 Streamlit Cloud 创建应用

1. 打开 **[share.streamlit.io](https://share.streamlit.io)**，用 **GitHub 账号** 登录。
2. 点击 **Create app**（或 New app）。
3. 填写：
   | 项 | 值 |
   |----|-----|
   | Repository | 选择刚推送的 `bxsimulator` |
   | Branch | `main` |
   | Main file path | `app/streamlit_app.py` |
4. **Advanced settings**（可选）：
   - Python version：**3.12**
5. 点击 **Deploy**，等待约 2–5 分钟构建。

## 第三步：发给同事

部署成功后地址类似：

`https://bxsimulator-xxxx.streamlit.app`

把该链接发给同事，浏览器打开即可使用，**无需安装 Python**。

## 更新版本

本地改完代码后：

```bash
git add .
git commit -m "更新说明"
git push
```

Streamlit Cloud 会自动重新部署（通常 1–3 分钟）。

## 常见问题

**构建失败：找不到 bxsimulator**  
确认仓库根目录有 `requirements.txt`，且最后一行是 `.`（安装本项目）。

**运行时报找不到 CSV**  
确认 `data/offline/regions/` 已提交到 Git（本次提交已包含）。

**国内访问慢**  
Streamlit 服务器在海外，可换手机热点或 VPN；若长期国内使用，可改方案二（Render / 内网 Docker）。

**免费版链接是公开的吗？**  
知道 URL 的人都能打开。勿输入真实客户敏感数据；如需鉴权可后续加密码或改内网部署。
