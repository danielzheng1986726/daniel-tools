"""
文件去重工具 - 测试数据生成器 V2（真实照片版）

使用方法：
1. 在本脚本同目录下创建 source_photos/ 文件夹
2. 往里面丢 8-10 张真实照片（jpg/png/heic 都行）
3. 运行：python3 generate_test_data_v2.py
4. 生成位置：./test_photos/

脚本会自动把你的照片按四种场景复制、重命名、分散到不同文件夹：
  场景1：完全重复（同名同内容，出现在多个文件夹）
  场景2：同名不同内容（名字一样但实际是不同照片——不能删！）
  场景3：内容相同但文件名不同（微信转发、多次保存的典型情况）
  场景4：独立文件（不重复，验证工具不会误删）
"""

import os
import shutil
import random
import hashlib

# ============================================================
# 配置
# ============================================================
SOURCE_DIR = "./source_photos"
OUTPUT_DIR = "./test_photos"
MIN_PHOTOS = 6

# 模拟真实的文件夹结构
FOLDER_STRUCTURE = {
    "iPhone导出_2024": ["2024春节", "2024暑假", "2024国庆"],
    "iPhone导出_2025": ["2025元旦", "2025春节"],
    "微信保存": [],
    "截图": [],
    "相机胶卷": [],
    "下载": [],
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".bmp", ".gif"}


# ============================================================
# 辅助函数
# ============================================================
def get_source_photos():
    """读取 source_photos/ 里的所有图片"""
    if not os.path.exists(SOURCE_DIR):
        os.makedirs(SOURCE_DIR)
        print(f"❌ 没有找到 {SOURCE_DIR}/ 文件夹，已自动创建。")
        print(f"   请往里面放 {MIN_PHOTOS}-10 张照片，然后重新运行此脚本。")
        return []

    photos = []
    for f in sorted(os.listdir(SOURCE_DIR)):
        ext = os.path.splitext(f)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            photos.append(os.path.join(SOURCE_DIR, f))
    return photos


def file_md5(filepath):
    with open(filepath, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()[:8]


def copy_file(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    return dst


def get_ext(filepath):
    return os.path.splitext(filepath)[1].lower()


# ============================================================
# 文件名生成器
# ============================================================
def iphone_name(index, ext):
    return f"IMG_{3000 + index:04d}{ext}"

def iphone_copy_name(index, ext):
    n = random.randint(1, 3)
    return f"IMG_{3000 + index:04d} ({n}){ext}"

def wechat_name(ext):
    ts = random.randint(1700000000, 1710000000)
    return random.choice([
        f"mmexport{ts}{ext}",
        f"microMsg_{random.randint(100, 999)}{ext}",
        f"wx_camera_{ts}{ext}",
    ])

def screenshot_name(ext):
    m, d = random.randint(1, 12), random.randint(1, 28)
    return f"Screenshot_2024{m:02d}{d:02d}_{random.randint(100000, 999999)}{ext}"

def download_name(index, ext):
    return random.choice([
        f"下载 ({index}){ext}",
        f"image ({index}){ext}",
        f"photo_{index:03d}{ext}",
    ])


# ============================================================
# 主逻辑
# ============================================================
def generate_test_data():
    photos = get_source_photos()
    if not photos:
        return

    if len(photos) < MIN_PHOTOS:
        print(f"❌ 需要至少 {MIN_PHOTOS} 张照片，当前只有 {len(photos)} 张。")
        print(f"   请往 {SOURCE_DIR}/ 里再加几张，然后重新运行。")
        return

    print(f"✅ 找到 {len(photos)} 张源照片：")
    for p in photos:
        print(f"   {os.path.basename(p)} ({file_md5(p)})")

    # 清理旧数据
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)

    # 创建文件夹结构
    all_folders = []
    for folder, subfolders in FOLDER_STRUCTURE.items():
        path = os.path.join(OUTPUT_DIR, folder)
        os.makedirs(path, exist_ok=True)
        all_folders.append(path)
        for sub in subfolders:
            subpath = os.path.join(path, sub)
            os.makedirs(subpath, exist_ok=True)
            all_folders.append(subpath)

    random.shuffle(photos)

    # 动态分配照片
    n = len(photos)
    s1_photos = photos[0:3]
    s2_photos = photos[3:6] if n >= 6 else photos[3:n]
    s3_photos = photos[6:9] if n >= 9 else photos[0:3]  # 不够就复用
    # 场景4用全部照片

    files_created = 0
    file_log = []

    # ----------------------------------------------------------
    # 场景1：完全重复（同名同内容，多个文件夹）
    # ----------------------------------------------------------
    print(f"\n{'='*60}")
    print("📁 场景1：完全重复的文件")
    print("   去重工具应该找到这些，只保留一份")
    print(f"{'='*60}")

    s1_folders = [
        os.path.join(OUTPUT_DIR, "iPhone导出_2024", "2024春节"),
        os.path.join(OUTPUT_DIR, "iPhone导出_2024", "2024暑假"),
        os.path.join(OUTPUT_DIR, "iPhone导出_2025", "2025元旦"),
        os.path.join(OUTPUT_DIR, "相机胶卷"),
        os.path.join(OUTPUT_DIR, "下载"),
    ]

    for i, photo in enumerate(s1_photos):
        ext = get_ext(photo)
        filename = iphone_name(i + 1, ext)
        md5 = file_md5(photo)
        targets = random.sample(s1_folders, 4)
        for folder in targets:
            dst = copy_file(photo, os.path.join(folder, filename))
            file_log.append((dst, md5, "场景1"))
            files_created += 1
        print(f"  ✅ {filename} (MD5: {md5}) → {len(targets)} 份完全相同的拷贝")

    # ----------------------------------------------------------
    # 场景2：同名但内容不同（不能删！）
    # ----------------------------------------------------------
    print(f"\n{'='*60}")
    print("📁 场景2：同名但内容不同")
    print("   ⚠️ 去重工具必须识别出这些是不同文件！")
    print(f"{'='*60}")

    s2_folders = [
        os.path.join(OUTPUT_DIR, "iPhone导出_2024", "2024国庆"),
        os.path.join(OUTPUT_DIR, "iPhone导出_2025", "2025春节"),
        os.path.join(OUTPUT_DIR, "微信保存"),
    ]

    conflict_base_names = ["IMG_5001", "度假照片", "重要截图"]

    for i, base_name in enumerate(conflict_base_names):
        if i >= len(s2_photos):
            break
        created = []
        for j, folder in enumerate(s2_folders):
            # 每个文件夹放不同的照片，但文件名一样
            src_idx = (i + j) % len(s2_photos)
            src = s2_photos[src_idx]
            ext = get_ext(src)
            filename = f"{base_name}{ext}"
            dst = copy_file(src, os.path.join(folder, filename))
            md5 = file_md5(src)
            file_log.append((dst, md5, "场景2"))
            files_created += 1
            created.append(f"{os.path.basename(folder)}({md5})")
        print(f"  ⚠️  {base_name}* → {', '.join(created)}")

    # ----------------------------------------------------------
    # 场景3：内容相同但文件名不同（核心演示点）
    # ----------------------------------------------------------
    print(f"\n{'='*60}")
    print("📁 场景3：内容相同但文件名不同")
    print("   这是去重工具最大的价值：找出隐藏的重复")
    print(f"{'='*60}")

    for i, photo in enumerate(s3_photos):
        ext = get_ext(photo)
        md5 = file_md5(photo)

        name_and_loc = [
            (
                iphone_copy_name(20 + i, ext),
                os.path.join(OUTPUT_DIR, "iPhone导出_2025", "2025春节")
            ),
            (
                wechat_name(ext),
                os.path.join(OUTPUT_DIR, "微信保存")
            ),
            (
                download_name(20 + i, ext),
                os.path.join(OUTPUT_DIR, "下载")
            ),
        ]

        created_names = []
        for name, folder in name_and_loc:
            dst_path = os.path.join(folder, name)
            counter = 1
            while os.path.exists(dst_path):
                base, extension = os.path.splitext(name)
                dst_path = os.path.join(folder, f"{base}_{counter}{extension}")
                counter += 1
            copy_file(photo, dst_path)
            file_log.append((dst_path, md5, "场景3"))
            files_created += 1
            created_names.append(os.path.basename(dst_path))

        print(f"  🔄 MD5 {md5} → {', '.join(created_names)}")

    # ----------------------------------------------------------
    # 场景4：独立文件（验证不误删）
    # ----------------------------------------------------------
    print(f"\n{'='*60}")
    print("📁 场景4：独立文件（不应该被删除）")
    print(f"{'='*60}")

    s4_folders = [
        os.path.join(OUTPUT_DIR, "截图"),
        os.path.join(OUTPUT_DIR, "iPhone导出_2024", "2024国庆"),
        os.path.join(OUTPUT_DIR, "iPhone导出_2025", "2025元旦"),
        os.path.join(OUTPUT_DIR, "相机胶卷"),
    ]

    for i, photo in enumerate(photos):
        ext = get_ext(photo)
        name = screenshot_name(ext) if i % 2 == 0 else f"IMG_E{8000 + i:04d}{ext}"
        folder = s4_folders[i % len(s4_folders)]
        dst_path = os.path.join(folder, name)
        counter = 1
        while os.path.exists(dst_path):
            base, extension = os.path.splitext(name)
            dst_path = os.path.join(folder, f"{base}_{counter}{extension}")
            counter += 1
        copy_file(photo, dst_path)
        md5 = file_md5(photo)
        file_log.append((dst_path, md5, "场景4"))
        files_created += 1

    print(f"  ✅ {len(photos)} 个独立文件分散在各文件夹中")

    # ----------------------------------------------------------
    # 统计报告
    # ----------------------------------------------------------
    print(f"\n{'='*60}")
    print(f"📊 生成完毕！")
    print(f"{'='*60}")
    print(f"源照片: {len(photos)} 张 → 生成文件: {files_created} 个")

    for scenario in ["场景1", "场景2", "场景3", "场景4"]:
        count = sum(1 for f in file_log if f[2] == scenario)
        print(f"  {scenario}: {count} 个文件")

    # 重复验证
    print(f"\n🔍 你的去重工具应该发现：")
    content_hashes = {}
    for filepath, _, _ in file_log:
        with open(filepath, 'rb') as f:
            full_md5 = hashlib.md5(f.read()).hexdigest()
        content_hashes.setdefault(full_md5, []).append(filepath)

    unique = sum(1 for v in content_hashes.values() if len(v) == 1)
    dup_groups = {k: v for k, v in content_hashes.items() if len(v) > 1}
    dup_files = sum(len(v) for v in dup_groups.values())
    can_delete = dup_files - len(dup_groups)

    print(f"  独立文件: {unique} 个")
    print(f"  重复组: {len(dup_groups)} 组（共 {dup_files} 个文件）")
    print(f"  可安全删除: {can_delete} 个")

    total_size = sum(os.path.getsize(f[0]) for f in file_log)
    if total_size > 1024 * 1024:
        print(f"\n💾 总大小: {total_size / (1024*1024):.1f} MB")
    else:
        print(f"\n💾 总大小: {total_size / 1024:.0f} KB")

    print(f"\n✅ 路径: {os.path.abspath(OUTPUT_DIR)}/")
    print(f"   用你的去重工具扫描这个路径即可录屏！")


if __name__ == "__main__":
    generate_test_data()
