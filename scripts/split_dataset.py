import os
import random
import shutil

random.seed(42)

# ===================== 这里核对路径！=====================
img_root = r"D:\YOLO11_ANPR\ccpd_raw\ccpd_green"
label_root = r"D:\YOLO11_ANPR\ccpd_raw\labels_green"
out_dir = r"D:\YOLO11_ANPR\plate_dataset"

train_ratio = 0.7
val_ratio = 0.2
test_ratio = 0.1
# =========================================================

# 创建输出目录
for split in ["train", "val", "test"]:
    os.makedirs(os.path.join(out_dir, "images", split), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "labels", split), exist_ok=True)

# 递归搜集全部jpg
img_list = []
for root, _, files in os.walk(img_root):
    for f in files:
        if f.lower().endswith(".jpg"):
            img_list.append(f)

random.shuffle(img_list)
total = len(img_list)
n_train = int(total * train_ratio)
n_val = int(total * val_ratio)

train_set = img_list[:n_train]
val_set = img_list[n_train:n_train + n_val]
test_set = img_list[n_train + n_val:]

def copy_files(file_list, split_name):
    for fname in file_list:
        # 在整个img_root下面找到这张图片的完整路径
        img_path = None
        for r, _, fs in os.walk(img_root):
            if fname in fs:
                img_path = os.path.join(r, fname)
                break
        if img_path is None:
            print(f"找不到图片：{fname}")
            continue

        txt_name = os.path.splitext(fname)[0] + ".txt"
        txt_src = os.path.join(label_root, txt_name)

        img_dst = os.path.join(out_dir, "images", split_name, fname)
        txt_dst = os.path.join(out_dir, "labels", split_name, txt_name)

        shutil.copy(img_path, img_dst)
        if os.path.exists(txt_src):
            shutil.copy(txt_src, txt_dst)
        else:
            print(f"缺失标签：{txt_name}")

copy_files(train_set, "train")
copy_files(val_set, "val")
copy_files(test_set, "test")

print(f"划分完成！")
print(f"总共：{total}")
print(f"train:{len(train_set)}")
print(f"val:{len(val_set)}")
print(f"test:{len(test_set)}")
