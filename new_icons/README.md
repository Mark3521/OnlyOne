# 新图标提交目录

每个新图标单独建立一个文件夹，例如 `new_icons/example_app/`，并放入：

- `config.json`：应用名称、包名、Activity 和 drawable 资源名。
- `fg.png`：432×432 RGBA 前景图。
- `bg.png`：432×432 RGBA 背景图。

配置示例见 `tools/templates/icon.json`。

## 添加图标

在仓库根目录执行：

```bash
python tools/add_icon.py new_icons/example_app --dry-run
python tools/add_icon.py new_icons/example_app
python tools/validate_icons.py
```

确认资源检查通过后提交变更。新图标必须使用 432×432、PNG color type 6（RGBA）的图片。
