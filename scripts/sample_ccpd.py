import os
import shutil
import random

if __name__ == '__main__':
    src_dir = r"D:\YOLO11_ANPR\ccpd_raw\ccpd_green"
    dst_dir = r"D:\YOLO11_ANPR\blue_add\ccpd_green"
    sample_num = 1500  # 每次抽取数量，可以改成1500
    os.makedirs(dst_dir, exist_ok=True)

    img_list = [f for f in os.listdir(src_dir) if f.endswith(".jpg")]
    random.shuffle(img_list)
    select = img_list[:sample_num]

    for fname in select:
        shutil.copy(os.path.join(src_dir, fname), os.path.join(dst_dir, fname))
    print(f"已经抽取 {len(select)} 张蓝牌到 blue_add/ccpd_green")
