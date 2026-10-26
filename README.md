# 南京大学电费监控脚本

这是一个用于监控南京大学电费充值页面剩余电量的Python脚本，并提供可视化网页面板。

[![仅20次电费变化曲线](data/recent_20_changes.png)](https://file+.vscode-resource.vscode-cdn.net/d%3A/Documents/Github/nju_electric_monitor/data/electricity_trend.png)

[![电费变化曲线](data/electricity_trend.png)](data/electricity_trend.png)

[点击查看电量数据表（CSV）](data/electricity_data.csv)

## 🌟功能特性

- 自动登录南京大学电费充值系统
- **支持两种验证方式**：传统验证码（ddddocr OCR）和滑块验证（captcha-recognizer AI识别）
- **自动检测验证方式**：智能识别当前页面是验证码还是滑块，自动切换处理流程
- **多轮重试机制**：传统验证码（外层×内层）和滑块验证（完整流程重试）确保高成功率
- **ChromeDriver 自动匹配**：本地版本不匹配时自动回退 Selenium Manager 下载
- 提取剩余电量信息
- 支持无头模式运行
- 数据保存为JSON和CSV格式
- 详细的日志记录
- **可视化网页面板，支持交互式电量曲线与数据表格**
- 一键批处理启动与网页自动打开

> 📖 **完整使用指南**：请查看 [GUIDE.md](GUIDE.md)，包含详细的安装部署、配置说明、验证机制详解、故障排除和开发指南。

## 🤖Github Actions 自动运行

本项目已集成 Github Actions 自动定时监控与数据更新，无需本地部署即可自动采集和推送电量数据。

### 本仓库采集与 Pages 发布

- `Auto Monitor Schedule` 按北京时间每天 03:00、09:00、15:00、21:00 请求运行；GitHub 定时调度可能延迟或丢弃，并非准点服务。
- 四个主调度分别声明；另在 03:17、09:17、15:17、21:17 做补采检查。所有定时触发先检查当前北京时间六小时采集时段，有有效新记录则跳过；手动和代码推送仍执行采集。补采同样依赖 GitHub 调度，不是外部独立监控，不能保证准点或修复平台层面完全不触发的问题。
- Runner 固定为 `ubuntu-24.04`，直接检查并使用预装且版本匹配的 Chrome/ChromeDriver，不再每次安装 Chromium。字体安装最多约 4 分钟，失败可降级；Python 依赖安装上限 8 分钟，整个采集作业上限 30 分钟。保留 pip 缓存以缩短后续启动时间。
- 也可在 Actions 手动运行；修改主分支的程序、网页、工作流或配置会自动执行一次采集。自动数据提交不会触发循环。
- 采集成功 → 校验恰好新增一条有效记录且 JSON/CSV 一致 → 提交并推送 → 部署同一数据提交的 Pages。部署不再使用独立 cron。
- 采集失败最多尝试 3 次，每次最多 4 分钟，间隔 15/30 秒；页面电量异步加载最多等待 30 秒。若失败时已经写入数据，直接报错而不重试，以免重复采集。采集、数据校验或推送失败均阻止自动发布；失败日志仍可在该次 Actions 的日志 artifact 中查看。
- 推送使用 GitHub 自动提供的 `GITHUB_TOKEN`（`contents: write`），不再依赖 `GIT_UPDATE_TOKEN`。若仓库规则禁止直接推送，任务会明确失败，不能静默跳过。
- 网页采集时间统一显示北京时间，后接 `(- xx day xx hour)`，每分钟更新；超过 12 小时标红并标注数据已过期。历史无时区时间按北京时间解释，新 JSON 记录显式携带 `+08:00`。
- `Deploy electricity dashboard` 保留手动发布入口，便于单独重发已有数据；它不会执行采集，也不会把旧数据变新。
- 离线回归检查：`python -B -m unittest discover -s src -p test_monitoring_checks.py -v` 和 `node --test site/dashboard.test.cjs`，均不会登录学校或发送邮件。

- 自动定时任务：每天多次自动运行，采集电量数据并推送到仓库。
- 自动安装 Python 依赖，按需补充中文字体，使用 runner 预装 Chrome/ChromeDriver。
- 自动生成数据文件和可视化图片。
- 运行日志和数据自动提交到仓库。

**如何启用/配置自动运行：**

1. 在仓库设置 Secrets，添加 `NJU_USERNAME` 和 `NJU_PASSWORD`。
2. config_workflow.json中可以配置参数，`NJU_USERNAME` 和 `NJU_PASSWORD`不变即可
3. Actions 会自动拉取凭据并运行，无需手动操作。
4. 可在 Actions 页面查看运行日志和结果。

config_workflow.json 部分参数：

- `captcha_retry_count`: 验证码识别重试次数（建议 3–10 次，当前示例为 4）
- `save_captcha_images`: 是否保存验证码图片用于调试（默认 true）
- `test_mode`: 是否在关键步骤保存页面快照到 `data/test_snapshots_workflow`（默认 false，仅调试时建议开启）
- `enable_email_alert`: 是否启用电量低于阈值时的邮件通知（默认 true）
- `alert_threshold_warn`: 一般提醒阈值（单位：度，默认 200）
- `alert_threshold_high`: 重要提醒阈值（单位：度，默认 10）
- `alert_threshold_critical`: 紧急提醒阈值（单位：度，默认 5）

## 🖥️本地运行方法

> 💡 **首次使用？** 建议先阅读 [完整使用指南 GUIDE.md](GUIDE.md)，包含详细的安装部署、配置说明和故障排除。

Github Actions 中已支持电量预警邮件：当剩余电量低于配置的阈值时，会自动发送带有近期电费曲线图的提醒邮件。

### 环境要求（本地运行）

- Python 3.9+（推荐 3.11，与 Github Actions 一致）
- Chrome浏览器
- ChromeDriver（已包含在chromedriver-win64目录中）

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 环境测试（推荐）

在运行主脚本之前，建议先运行环境测试：

```bash
python tests/test_environment.py
```

### 3. 解决PIL兼容性问题（重要）

如果遇到 `module 'PIL.Image' has no attribute 'ANTIALIAS'` 错误，请运行：

```bash
python src/fix_pil_compatibility.py
```

### 4. 准备ChromeDriver

确保项目根目录下有 `chromedriver-win64` 文件夹，并包含 `chromedriver.exe` 文件。

### 5. 配置脚本

首次运行时会自动创建 `config.json` 配置文件，或者手动创建：

- `captcha_retry_count`: 验证码识别重试次数（默认5次）
- `save_captcha_images`: 是否保存验证码图片用于调试（默认true）

```json
{
    "username": "你的用户名",
    "password": "你的密码",
    "auto_login": true,
    "headless_mode": true,
   "captcha_retry_count": 5,
   "save_captcha_images": true,
    "log_level": "INFO"
}
```

### 6. 运行主监控脚本

#### 方法1：使用批处理文件（推荐）

```bash
run_auto_monitor.bat
```

#### 方法2：直接运行Python脚本

```bash
python src/nju_electric_monitor_auto.py
```

或指定配置文件：

```bash
python src/nju_electric_monitor_auto.py config.json
```

### 7. 启动可视化网页面板

#### 推荐方式：一键批处理启动

```bash
run_web_panel.bat
```

- 会自动激活虚拟环境并启动网页服务
- 自动用Edge或Chrome浏览器打开 http://127.0.0.1:5000/
- 支持桌面快捷方式

#### 手动方式

```bash
python src/web_panel.py
```

然后浏览器访问 http://127.0.0.1:5000/

### 8. 调试与测试工具

- 页面结构调试：
  ```bash
  python tests/debug_page_structure.py
  ```
- 验证码识别测试：
  ```bash
  python tests/test_captcha_recognition.py
  ```

## 📄输出文件

- `data/electricity_data.json`：电量数据（JSON 行格式）
- `data/electricity_data.csv`：电量数据（CSV 格式，列为 time/num/unit）
- `data/electricity_trend.png`：完整历史电量变化曲线图
- `data/recent_20_changes.png`：最近 20 次电量变化曲线图（workflow/auto 版本）
- `data/captcha_debug.png`：最近一次验证码截图（用于快速查看验证码样式）
- `data/captcha_auto/*.png`：本地 auto 版本每轮重试保存的验证码图片，识别成功后会按识别结果重命名为 `PCET.png` 等
- `data/captcha_workflow/*.png`：GitHub Actions workflow 运行时每轮重试保存的验证码图片，识别成功后同样按识别结果重命名
- `logs/nju_electric_monitor-YYYY-MM-DD-HH.log`：主脚本按小时滚动生成的运行日志
- `logs/workflow_wrapper_*.log`：CI 包装脚本输出的完整运行日志（包含环境信息、字体诊断等）

## 🏁网页面板功能

- 实时展示电量变化曲线（可缩放、拖动、悬停查看数据）
- 数据表格美观展示，支持一键刷新
- 科技感UI设计，适配桌面与移动端

## 💡注意事项

1. 建议优先使用 Github Actions 自动运行，无需本地部署。
2. 本地运行时确保Chrome浏览器版本与ChromeDriver版本兼容。
3. 如果验证码识别失败，脚本会提示手动输入。
4. 建议在无头模式下运行以提高性能。
5. 请妥善保管登录凭据。
6. **重要**：如遇PIL兼容性问题，请运行 `src/fix_pil_compatibility.py`
7. 如果无法提取电量信息，请运行 `tests/debug_page_structure.py` 分析页面结构。
8. 如果验证码识别不正确，请运行 `tests/test_captcha_recognition.py` 测试识别效果。

## 🔐故障排除

### PIL兼容性问题（常见）

如果遇到 `module 'PIL.Image' has no attribute 'ANTIALIAS'` 错误：

1. **运行修复脚本**：

   ```bash
   python src/fix_pil_compatibility.py
   ```
2. **手动修复**：在脚本开头添加：

   ```python
   from pil_compatibility_patch import *
   ```
3. **降级Pillow版本**（如果修复脚本不起作用）：

   ```bash
   pip install Pillow==9.5.0
   ```

### 环境问题

如果遇到环境配置问题：

1. 运行 `python tests/test_environment.py` 检查环境配置
2. 确保所有依赖正确安装：`pip install -r requirements.txt`
3. 检查Python版本是否满足要求（建议 >= 3.9，推荐 3.11）

### ChromeDriver问题

如果遇到ChromeDriver相关错误，请检查：

1. `chromedriver-win64/chromedriver.exe` 文件是否存在
2. ChromeDriver版本是否与Chrome浏览器版本匹配
3. **脚本已内置自动回退**：本地版本不匹配时，会自动使用 Selenium Manager 下载匹配版本
4. 如需手动更新，下载对应版本: https://chromedriver.chromium.org/downloads

### OCR识别问题

如果验证码识别失败：

1. 检查网络连接
2. 确保 ddddocr 安装成功（`pip install -r requirements.txt` 会自动安装）
3. 尝试手动输入验证码
4. 运行 `python tests/test_captcha_recognition.py` 测试识别效果
5. 适当调大 `captcha_retry_count` 或查看 `data/captcha_auto` / `data/captcha_workflow` 中的验证码截图，人工比对识别结果

### 滑块验证问题

如果滑块验证失败：

1. 确保 captcha-recognizer 已安装（`pip install -r requirements.txt`）
2. 运行滑块验证测试：`python tests/test_verification_flow.py`
3. 滑块验证已内置多轮重试（默认3轮），单次失败会自动重新截取、识别、拖拽
4. 查看日志中 `滑块缺口 box=` 信息，确认缺口检测是否准确

### 电量信息提取问题

如果无法提取电量信息：

1. 运行 `python tests/debug_page_structure.py` 分析页面结构
2. 根据分析结果调整脚本中的选择器

### 验证码识别问题

如果验证码识别不正确：

1. 运行 `python tests/test_captcha_recognition.py` 测试不同的图像处理方法
2. 查看生成的调试图片，选择最清晰的处理方法
3. 适当调大 `captcha_retry_count`，或直接在本地通过手动输入验证码兜底

## 许可证

MIT License
