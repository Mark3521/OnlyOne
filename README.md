# OnlyOne Icon Pack

OnlyOne 是一个 Android Adaptive Icon 图标包，原项目主要用于补全未适配 Adaptive Icon 的应用图标。原始项目说明仅记录了在 Lawnchair 12 上测试的情况；其他启动器的兼容性需要自行验证。

本 Fork 在保留原有 Android 资源、应用映射和 Gradle 配置的基础上，增加了图标添加自动化、资源完整性检查和 GitHub Actions APK 编译。

## 项目环境

本次自动化维护改造保留原项目的 Android 构建参数，不主动升级 Android Gradle Plugin 或 SDK：

| 项目 | 配置 |
|---|---|
| Android Gradle Plugin | 7.1.3 |
| Gradle（GitHub Actions） | 7.2 |
| JDK | 11 |
| compileSdk | 31 |
| minSdk | 30 |
| targetSdk | 31 |
| applicationId | `com.android.iconpack.onlyone` |
| Java | 8 |

## 新增一个图标

### 1. 准备目录

在 `new_icons/` 下为新应用建立独立目录，例如：

```text
new_icons/
└── example_app/
    ├── fg.png
    ├── bg.png
    └── config.json
```

图片要求：

- `fg.png`：图标前景，432×432 px、RGBA PNG，建议主体外保留透明区域。
- `bg.png`：图标背景，432×432 px、RGBA PNG。
- 两张图必须是 PNG color type 6（RGBA），且带有 alpha 通道。

### 2. 填写 config.json

可复制 `tools/templates/icon.json` 后修改：

```json
{
  "name": "Example App",
  "package": "com.example.app",
  "activity": "com.example.app.MainActivity",
  "drawable": "example_app"
}
```

字段说明：

| 字段 | 必填 | 说明 |
|---|---|---|
| `name` | 是 | 应用显示名称，用于 appfilter 注释 |
| `package` | 是 | Android 应用包名 |
| `activity` | 二选一 | 一个启动 Activity，可以是完整类名或 `.MainActivity` 形式 |
| `activities` | 二选一 | 多个 Activity 的字符串数组 |
| `drawable` | 否 | Android drawable 资源名；省略时由应用名称生成 |

如果一个应用有多个桌面入口，可以使用：

```json
{
  "name": "Example App",
  "package": "com.example.app",
  "activities": [
    ".MainActivity",
    "com.example.app.SecondActivity"
  ],
  "drawable": "example_app"
}
```

Activity 必须属于所填写的 package。请先通过设备包管理器、ADB 或应用清单确认真实启动 Activity，不要直接照抄示例类名。

### 3. 预检查与添加

在仓库根目录执行：

```bash
python tools/add_icon.py new_icons/example_app --dry-run
```

确认输出的目标资源和 Activity 无误后，正式添加：

```bash
python tools/add_icon.py new_icons/example_app
```

工具会自动完成：

1. 检查 config.json、前景图和背景图。
2. 检查 PNG 尺寸、RGBA 格式和透明通道。
3. 将 PNG 复制到 `app/src/main/res/drawable-xxxhdpi/`。
4. 生成 `drawable-anydpi-v26/<drawable>.xml`。
5. 将 Activity 映射追加到 `xml/appfilter.xml`。
6. 将图标添加到 `xml/drawable.xml` 对应首字母分类。
7. 检查图标名称和 Activity 是否已存在，避免重复注册。

脚本不会自动修改 `MainActivity.java`、Manifest 或 `values/icon_pack.xml`。后者是原项目单独维护的资源数组，不等同于图标展示列表。

### 4. 检查整个图标资源库

```bash
python tools/validate_icons.py
```

检查内容包括：

- XML 文件是否能够解析。
- Adaptive Icon 是否包含有效的 drawable 前景/背景引用。
- `appfilter.xml` 中的 drawable 是否存在。
- `drawable.xml` 中的图标是否存在。
- PNG 是否能够读取，并检查尺寸、色彩类型和透明通道。
- 重复 Activity 映射、重复展示项和未进入展示列表的 Adaptive Icon。

**历史资源兼容说明：** 原始 ZIP 中已经存在少量历史不规范资源，例如非 432×432 的 PNG、非 RGBA PNG、重复展示项和重复 Activity 映射。检查工具会将这些现存情况列为 `[WARN]`，不会擅自重采样、删除或改写原图；新增图标则严格执行 432×432 RGBA 要求。真正缺失的资源引用或 XML 错误会以 `[ERROR]` 报告并使检查失败。

## GitHub Actions

仓库包含两个工作流：

- `Validate icon resources`：Push、Pull Request 或手动触发时运行资源检查。
- `Build Android APK`：推送到 `main` / `master` 或手动触发时，先检查资源，再构建 Debug 和 Release APK，并上传为 Actions Artifact。

### 获取 APK

1. 将 Fork 推送到 GitHub。
2. 打开仓库的 **Actions** 页面。
3. 进入 **Build Android APK** 工作流。
4. 等待任务完成，在运行记录底部的 **Artifacts** 下载 `OnlyOne-<commit-sha>`。
5. 解压后选择 APK 安装测试。

Debug APK 使用 Android Gradle 默认的 debug 签名，适合个人安装测试。Release APK 当前没有配置个人签名密钥，构建产物为未签名 APK；若要正式分发或覆盖安装，需要后续配置自己的签名密钥和 GitHub Secrets。不要把 keystore 或密码提交到仓库。

## 本地编译

原始 ZIP 未包含 Gradle Wrapper。GitHub Actions 会安装指定的 Gradle 7.2，因此云端构建不依赖 Wrapper。若在本地编译，需要安装 JDK 11 和 Gradle 7.2，然后在仓库根目录执行：

```bash
gradle assembleDebug
```

或同时构建 Debug 和 Release：

```bash
gradle assembleDebug assembleRelease
```

APK 输出目录：

```text
app/build/outputs/apk/debug/
app/build/outputs/apk/release/
```

## 原项目资源结构

| 路径 | 用途 |
|---|---|
| `app/src/main/res/drawable-xxxhdpi/` | 图标前景与背景 PNG |
| `app/src/main/res/drawable-anydpi-v26/` | Adaptive Icon XML |
| `app/src/main/res/xml/appfilter.xml` | Activity 到 drawable 的映射 |
| `app/src/main/res/xml/drawable.xml` | 图标包展示列表及分类 |
| `app/src/main/res/values/icon_pack.xml` | 原项目单独维护的图标资源数组 |

## 致谢

- 原项目：HowieHChen/OnlyOne
- 参考项目：NanoIconPack

请保留原项目的许可、版权和致谢信息。新增图标素材应确保你拥有使用和分发权限。
