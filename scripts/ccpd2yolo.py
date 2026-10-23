import os
import cv2

def ccpd_to_yolo(img_path, save_label_path):
    name = os.path.basename(img_path)
    parts = name.split("-")
    bbox_part = parts[2]

    # 兼容两种格式：
    # 蓝牌：123_456_789_999
    # 绿牌：123&456_789&999
    if "&" in bbox_part:
        p1, p2 = bbox_part.split("_")
        x1, y1 = p1.split("&")
        x2, y2 = p2.split("&")
    else:
        x1, y1, x2, y2 = bbox_part.split("_")

    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)

    img = cv2.imread(img_path)
    h, w = img.shape[:2]

    xc = (x1 + x2) / 2 / w
    yc = (y1 + y2) / 2 / h
    bw = (x2 - x1) / w
    bh = (y2 - y1) / h

    with open(save_label_path, "w", encoding="utf-8") as f:
        f.write(f"0 {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}\n")


if __name__ == "__main__":
    # ========== 修改这里路径 ==========
    img_source = r"D:\YOLO11_ANPR\ccpd_raw\ccpd_green"
    label_save_dir = r"D:\YOLO11_ANPR\ccpd_raw\labels_green"
    # ==================================

    os.makedirs(label_save_dir, exist_ok=True)
    count = 0
    error_count = 0
    for root, _, files in os.walk(img_source):
        for fname in files:
            if fname.lower().endswith(".jpg"):
                img_full = os.path.join(root, fname)
                txt_name = fname.replace(".jpg", ".txt")
                txt_full = os.path.join(label_save_dir, txt_name)
                try:
                    ccpd_to_yolo(img_full, txt_full)
                    count += 1
                except Exception as e:
                    error_count += 1
                    print(f"跳过异常文件：{fname},err:{e}")
    print(f"转换完成，成功生成 {count} 个标签，跳过异常文件 {error_count} 个")
