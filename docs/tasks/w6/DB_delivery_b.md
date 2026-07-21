# 交付 B（DB） W6 任务书

> 周期：8/24（周日）- 8/31（周六） | 核心目标：视频最终修改、提交材料中的视频准备、答辩支持

## 每日任务

### Day 1（8/24 周日）— 全员 Review 会议

- [ ] 参加全员 review 会议
- [ ] 记录视频的修改意见（节奏、画面、字幕、旁白）
- [ ] 整理修改清单，按优先级排序

**验证：**
```bash
# 确认修改清单已记录
type demo\修改清单.md
# 预期：包含至少 3 条修改意见
```

### Day 2（8/25 周一）— 视频最终修改

- [ ] 根据 review 意见调整视频节奏和画面
- [ ] 修复画面/字幕问题，确认旁白与画面对齐
- [ ] 确认总时长 5-8 分钟（不超过 8 分钟）
- [ ] 重新渲染最终版

```bash
# 重新渲染
ffmpeg -i demo/output/fine_cut_v2.mp4 -c:v libx264 -preset slow -crf 20 -r 30 -vf scale=1920:1080 -c:a aac -b:a 192k demo/output/final_demo_v2.mp4
```

**验证：**
```bash
ffprobe -v quiet -show_entries format=duration demo/output/final_demo_v2.mp4
# 预期：duration 300-480s（5-8 分钟）
```

### Day 3（8/26 周二）— 视频质量最终检查

- [ ] 逐项检查：分辨率 1920×1080、格式 MP4 (H.264)、大小 < 500MB
- [ ] 确认音画同步、字幕无错别字
- [ ] 输出到 `demo/output/final_demo_v2.mp4`，发给 TL 最终确认

```bash
ffprobe -v quiet -show_entries stream=width,height,codec_name,r_frame_rate -show_entries format=size,duration demo/output/final_demo_v2.mp4
```

**验证：**
```bash
ffprobe -v quiet -show_entries stream=width,height,codec_name -show_entries format=size demo/output/final_demo_v2.mp4
# 预期：width=1920, height=1080, codec_name=h264, size < 524288000
```

### Day 4（8/27 周三）— 视频提交版本准备

- [ ] 确认比赛平台对视频格式/大小的要求
- [ ] 如果需要压缩，用 ffmpeg 调整码率：`ffmpeg -i final_demo_v2.mp4 -b:v 5M final_submit.mp4`
- [ ] 准备视频封面图（第一帧截图）
- [ ] 确认所有图表文件在仓库中

```bash
# 提取封面图
ffmpeg -i demo/output/final_demo_v2.mp4 -vframes 1 -q:v 2 demo/output/cover.jpg
# 如需压缩
ffmpeg -i demo/output/final_demo_v2.mp4 -c:v libx264 -b:v 5M -c:a aac -b:a 128k demo/output/final_submit.mp4
```

**验证：**
```bash
dir demo\output\cover.jpg
# 预期：文件存在，为 1920×1080 JPEG
dir demo\output\final_submit.mp4
# 预期：文件存在，符合平台大小要求
```

### Day 5（8/28 周四）— demo/ 目录整理

- [ ] 整理 `demo/` 目录最终状态：output/final_demo.mp4、视频脚本.md、assets/
- [ ] 删除过大的中间文件（保留最终版即可）
- [ ] 确认目录结构干净、完整

```bash
# 清理中间文件（保留最终版）
del demo\output\rough_cut.mp4
del demo\output\fine_cut.mp4
# 最终目录结构
dir /s /b demo\output\
```

**验证：**
```bash
dir demo\output\
# 预期：仅包含 final_demo_v2.mp4, final_submit.mp4, cover.jpg
dir demo\视频脚本.md
# 预期：文件存在
```

### Day 6（8/29 周五）— 模拟答辩支持

- [ ] 参加模拟答辩
- [ ] 负责答辩中的视频播放环节：确认播放设备兼容、准备备用 U 盘、确认音量/投影效果
- [ ] 如果答辩需要现场演示系统，准备演示环境

```bash
# 确认视频可在标准播放器中打开
start demo\output\final_demo_v2.mp4
# 复制到 U 盘备用
xcopy demo\output\final_demo_v2.mp4 E:\backup\ /Y
```

**验证：**
```bash
# 确认 U 盘备份存在
dir E:\backup\final_demo_v2.mp4
# 预期：文件存在（如 U 盘已插入）
```

### Day 7（8/30-8/31）— 最终提交 / Buffer

- [ ] 8/30：协助最终提交，确认视频上传成功
- [ ] 8/31：Buffer，处理遗留问题

**验证：**
```bash
# 确认提交平台上视频可播放（手动确认）
echo "视频已上传至比赛平台，可在线播放"
```

## 交付物

| 文件 | 截止日 | 验收标准 |
|------|--------|----------|
| 视频最终修改 | 8/25 | 根据 review 反馈调整，5-8 分钟 |
| 视频质量检查 | 8/26 | 1080p / H.264 MP4 / < 500MB / 音画同步 |
| 视频提交版本 | 8/27 | 符合平台格式和大小要求，含封面图 |
| demo/ 目录整理 | 8/28 | 干净、完整，无冗余中间文件 |
| 答辩视频播放准备 | 8/29 | 设备兼容，U 盘备份就绪 |

## 协作对接

- 与 TL 确认视频最终版定版（Day 3）
- 与 DA 确认提交平台要求和上传流程（Day 4）
- 答辩前与全员确认播放环节分工（Day 6）
