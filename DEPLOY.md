# 线上部署指南

把 **分红产品投资仿真器** 部署到公网或公司内网，同事通过浏览器访问，无需本地安装。

离线区域数据已打包在 `data/offline/`，部署后**不需要**外网行情 API。

---

## 方案一：Streamlit Community Cloud（最简单）

适合：快速试用、团队可访问 GitHub、对访问控制要求不高（免费版为公开链接）。

1. **将项目推到 GitHub**（私有或公开仓库均可）
   ```bash
   cd Simulator
   git init
   git add .
   git commit -m "Initial commit for deployment"
   git branch -M main
   git remote add origin https://github.com/<你的组织>/bxsimulator.git
   git push -u origin main
   ```

2. 打开 [share.streamlit.io](https://share.streamlit.io)，用 GitHub 登录。

3. **New app** → 选择仓库 → 设置：
   - **Main file path**：`app/streamlit_app.py`
   - **Python version**：3.11 或 3.12

4. 点击 **Deploy**。构建会使用根目录的 `requirements.txt`（已包含 `.` 以安装本项目）。

5. 部署完成后获得形如 `https://<app>.streamlit.app` 的地址，发给同事即可。

> 国内访问 Streamlit Cloud 可能较慢或被墙，见方案二/三。

---

## 方案二：Docker（推荐，国内外通用）

适合：Railway、Render、公司服务器、阿里云 ECS 等任何支持容器的平台。

### 本地验证

```bash
docker build -t bxsimulator .
docker run --rm -p 8501:8501 bxsimulator
```

浏览器打开 `http://localhost:8501`。

### Render（一键）

1. 代码推到 GitHub。
2. 登录 [render.com](https://render.com) → **New** → **Blueprint** → 连接仓库。
3. 仓库内已有 `render.yaml`，按提示部署即可。

### Railway

1. 登录 [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**。
2. 选择本仓库；Railway 会自动识别 `Dockerfile`。
3. 在 **Settings** 中生成公共域名，端口 **8501**。

### 公司内网服务器

```bash
git clone <仓库地址> /opt/bxsimulator
cd /opt/bxsimulator
docker build -t bxsimulator .
docker run -d --name bxsimulator -p 8501:8501 --restart unless-stopped bxsimulator
```

用 Nginx 反代到 `http://127.0.0.1:8501`，并配置 HTTPS / VPN，仅内网可访问。

---

## 方案三：仅 Python 环境（无 Docker）

在 Linux 服务器上：

```bash
git clone <仓库地址>
cd bxsimulator
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export BXSIMULATOR_ROOT=$(pwd)
streamlit run app/streamlit_app.py --server.address=0.0.0.0 --server.port=8501
```

生产环境建议用 **systemd** 或 **supervisor** 守护进程，前面加 Nginx。

---

## 环境变量

| 变量 | 说明 |
|------|------|
| `BXSIMULATOR_ROOT` | 项目根目录（含 `data/`、`configs/`）。Docker 镜像内已设为 `/app`。 |

---

## 部署前检查

```bash
pip install -e ".[ui,dev]"
pytest
```

确认 `data/offline/regions/*.csv` 已纳入 Git（离线回测依赖这些文件）。

---

## 访问与安全

- **免费 Streamlit Cloud**：应用 URL 为公开链接，勿在界面中输入真实客户敏感数据。
- **内部使用**：优先 Docker + 公司内网 / VPN，或 Render/Railway 仅分享链接给同事。
- 若需登录鉴权，可在后续增加 `streamlit-authenticator` 或反向代理统一认证。

---

## 常见问题

**Q：部署后提示找不到区域数据 CSV？**  
A：确认 `data/offline/regions/` 已提交到 Git，且设置了 `BXSIMULATOR_ROOT` 或从项目根目录启动。

**Q：同事打不开链接？**  
A：检查防火墙、是否需 VPN；国内可改用 Render / 自建服务器。

**Q：和本地 `bxsim-web.bat` 功能一致吗？**  
A：一致。线上版使用相同 `app/streamlit_app.py` 与离线区域数据包。
