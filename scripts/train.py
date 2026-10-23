from ultralytics import YOLO

if __name__ == '__main__':
    # 加载YOLO11n轻量化模型，适合1650显卡
    model = YOLO("yolo11n.pt")

    # 开始训练
    results = model.train(
        data=r"D:\YOLO11_ANPR\plate.yaml",
        epochs=30,
        imgsz=640,
        batch=4,   # GTX1650显存小，batch不要开大！4或者2
        device=0,  # 使用GPU
        patience=10,
        save=True,
        workers=0
    )
