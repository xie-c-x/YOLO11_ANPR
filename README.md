# YOLO11 车牌识别（ANPR）

YOLO11 负责“找车牌”，RapidOCR 负责“读车牌号”。

> 检测模型已经训练完成（`scripts/runs/detect/train/weights/best.pt`，验证集 mAP50≈0.92），
> **不需要重新训练**。下面都是推理和环境相关的改动。

## 两个入口

| 脚本 | 用途 |
| --- | --- |
| `scripts/anpr_predict.py` | 图片识别（单张或整个目录） |
| `scripts/anpr_full.py` | 摄像头 / 视频实时识别 |

公共代码在 `scripts/plate_utils.py`：模型加载、裁剪、OCR、车牌校正、中文绘制。

## 环境：用对解释器

项目的依赖装在 conda 环境 **`yolo11_anpr`** 里：

```
C:\Users\11037\.conda\envs\yolo11_anpr\python.exe
```

不要直接用 `python`（它指向 Windows 商店的占位程序，运行会失败），也不要用
`D:\anaconda3\python.exe`（base 环境没有 ultralytics/rapidocr）。

VS Code 已经在 `.vscode/settings.json` 里固定解释器；命令行里可以先激活环境：

```powershell
conda activate yolo11_anpr
```

### 环境自检

```powershell
python scripts/check_env.py
```

会检查解释器、依赖、GPU、模型权重、数据集、中文字体，并列出冲突。

### 已定位的冲突

1. **PaddleOCR 2.7 + PaddlePaddle 3.3 不兼容**
   旧版 PaddleOCR 在 Paddle 3.x 下会报
   `OneDnnContext does not have the input Filter / fused_conv2d`。
   两个脚本已改用 RapidOCR，不再依赖 Paddle。
   如果不再用 Paddle，可以卸载（可选）：

   ```powershell
   python -m pip uninstall -y paddleocr paddlepaddle
   ```

2. **同时装了多个 OpenCV**
   当前 `opencv-python 4.8.1.78` 和 `opencv-contrib-python 4.6.0.66` 并存，
   `cv2` 实际加载的是 4.8.1。现在能用，但建议只保留一个（清理会重装，见下）：

   ```powershell
   python -m pip uninstall -y opencv-python opencv-contrib-python
   python -m pip install opencv-python==4.8.1.78
   ```

3. **`scripts/4.7.0` 是误存的 pip 日志**，不是依赖文件，可以删。

## 用法

### 图片识别

```powershell
# 默认识别 test_img/car2.jpg
python scripts/anpr_predict.py

# 单张
python scripts/anpr_predict.py test_img/car1.jpg

# 整个目录，不弹窗
python scripts/anpr_predict.py test_img --no-show

# 保存车牌小图，方便排查识别错误
python scripts/anpr_predict.py test_img/car3.jpg --save-crops result_img/crops
```

结果默认保存为 `result_img/<原文件名>_anpr.jpg`。

常用参数：

- `--conf 0.5`：检测阈值，漏检可降到 0.3，误检可升到 0.7
- `--imgsz 640`：小目标可调到 960（更慢）
- `--device auto|cpu|0`
- `--no-show`：不弹预览窗口
- `--debug`：打印每个框的 OCR 原始结果

### 摄像头 / 视频实时识别

```powershell
# 默认摄像头 0，按 q/ESC 退出
python scripts/anpr_full.py

# 第二个摄像头
python scripts/anpr_full.py 1

# 识别视频文件
python scripts/anpr_full.py test.mp4

# 无窗口跑 100 帧并录像
python scripts/anpr_full.py --no-show --max-frames 100 --save-video result_img/demo.mp4

# 摄像头默认分辨率帧率最高；要高清再手动指定
python scripts/anpr_full.py --width 1280 --height 720
```

画面左上角显示 FPS 和当前车牌数；车牌文字用 PIL + 微软雅黑绘制，
所以汉字不会变成 `???`。

## 这次修了什么

**anpr_full.py（摄像头）**

- 原脚本读的是 `test_img/car10.jpg` 静态图，并不会开摄像头；已改成真正的
  `cv2.VideoCapture` 实时循环。
- OCR 只要识别（`use_det=False`），不再对车牌小图重复做文本检测：
  约 **600ms → 13ms**。
- 车牌小图放大到 64px 高再识别，小图识别率明显提升。
- 摄像头后端优先 MSMF（这台机器实测 30fps，DirectShow 只有 10fps）。
- 摄像头返回的 `frame` 直接送 YOLO 会慢十几倍（250ms），
  已先 `np.ascontiguousarray` 复制（降到 ~34ms/帧）。
- 跨帧 IoU 匹配缓存识别结果，画面不再每帧跳字。
- 支持录像、FPS 显示、`q/ESC` 退出、摄像头打不开的中文提示。

**anpr_predict.py（图片）**

- 去掉 PaddleOCR（版本冲突根源），统一用 RapidOCR。
- 去掉没用的 `numpy` 导入和写死的调试输出。
- 修正 `plate_post_correct`：
  - 不再把合法的 `Q` 改成 `0`（如 `京Q`）；
  - `O→0`、`I→1` 只作用在第 3 位以后；
  - 去掉 `·` 分隔符；
  - 多读出一位时，自动截取合法的 7/8 位车牌窗口。
- 中文车牌用 PIL 绘制，不再显示成 `???`。
- 支持中文路径（`cv2.imread/imwrite` 在 Windows 下遇到中文路径会失败）。
- 支持目录批量、`--save-crops`、`--no-show`、`--debug`。

## 数据集与训练文件

- `plate_dataset/`：train 2100 / val 600 / test 300，图片和标签一一对应，
  类别只有 `0: license_plate`，标签坐标都在 `[0,1]`，检查通过。
- `plate.yaml` 只声明了 train/val，`test` 目录用于自己评估，不影响训练。
- `scripts/train.py` 不用再跑。
- `scripts/ccpd2yolo.py`、`scripts/split_dataset.py` 是生成数据集时用的，
  当前数据已经就绪，不必重跑。
  （注意 `split_dataset.py` 只读 `ccpd_green`，而现有 3000 张是
  `ccpd_base + ccpd_green` 合起来的，重跑会得到不同的划分。）
- `scripts/ch_PP-OCRv3_rec_plate/` 是 PaddleOCR 的识别模型，目前没有用到；
  现在两个脚本都用 RapidOCR 自带模型。
