# 交付 B（DB） W5 任务书

> 周期：8/17（周日）- 8/23（周六） | 核心目标：视频录制与剪辑、最终图表确认

## 每日任务

### Day 1（8/17 周日）— 素材齐全确认

- [ ] 确认路口 16 原始流量对比素材（FixedTime vs CA-MP）已就绪
- [ ] 确认路口 16 1.5 倍流量对比素材已就绪
- [ ] 确认云-边-端消息流动画、指标对比图表动画、雄安背景素材已就绪
- [ ] 如有缺失素材，今天补录

```bash
# 素材检查清单
dir demo\assets\recordings\fixed_time_i16.mp4
dir demo\assets\recordings\ca_mp_i16.mp4
dir demo\assets\recordings\fixed_time_i16_1.5x.mp4
dir demo\assets\recordings\ca_mp_i16_1.5x.mp4
dir demo\assets\charts\animation_i16.mp4
dir demo\assets\background\
```

**验证：**
```bash
for %f in (demo\assets\recordings\fixed_time_i16.mp4 demo\assets\recordings\ca_mp_i16.mp4 demo\assets\recordings\fixed_time_i16_1.5x.mp4 demo\assets\recordings\ca_mp_i16_1.5x.mp4) do @if exist %f (echo OK: %f) else (echo MISSING: %f)
# 预期：全部输出 OK，无 MISSING
```

### Day 2（8/18 周一）— 旁白录制

- [ ] 按 DA 的旁白稿逐段录音（或 AI 配音），每段单独录制方便后期对齐
- [ ] 确认音质清晰、语速适中（约 200 字/分钟）
- [ ] 录制 SUMO-GUI 最终版素材（如需更新）
- [ ] 旁白文件按段落命名：`demo/assets/recordings/narration_01.mp3` ... `narration_06.mp3`

**验证：**
```bash
ffprobe -v quiet -show_entries format=duration demo/assets/recordings/narration_01.mp3
# 预期：duration 30-60s（对应 0:00-0:45 段落）
dir demo\assets\recordings\narration_*.mp3 | find /c ".mp3"
# 预期：6（对应 6 段旁白）
```

### Day 3（8/19 周二）— 视频粗剪

- [ ] 按视频脚本 6 段结构拼接：问题引入→方案概述→系统演示→数据说话→云端协同→总结
- [ ] 对齐旁白和画面，添加字幕（关键数据、创新点关键词）
- [ ] 目标：7 分钟粗剪版
- [ ] 发给 TL 和 DA 预览

```bash
# 用 ffmpeg 预拼接片段（如用剪映/Premiere 则跳过）
ffmpeg -f concat -safe 0 -i demo/filelist.txt -c copy demo/output/rough_cut.mp4
ffprobe -v quiet -show_entries format=duration demo/output/rough_cut.mp4
```

**验证：**
```bash
ffprobe -v quiet -show_entries format=duration demo/output/rough_cut.mp4
# 预期：duration 390-480s（6.5-8 分钟）
```

### Day 4（8/20 周三）— 视频精剪

- [ ] 根据 TL/DA 反馈调整节奏（哪里太快/太慢）
- [ ] 补充缺失画面，优化转场
- [ ] 添加背景音乐（轻量、不抢旁白）
- [ ] 输出精剪版 `demo/output/fine_cut.mp4`

**验证：**
```bash
ffprobe -v quiet -show_entries format=duration demo/output/fine_cut.mp4
# 预期：duration 300-480s（5-8 分钟）
```

### Day 5（8/21 周四）— 视频最终渲染

- [ ] 最终渲染参数：1920×1080，MP4 (H.264)，30fps，< 500MB
- [ ] 输出到 `demo/output/final_demo.mp4`
- [ ] 发给 TL 最终确认

```bash
# 最终渲染（剪映/Premiere 导出或 ffmpeg 转码）
ffmpeg -i demo/output/fine_cut.mp4 -c:v libx264 -preset slow -crf 20 -r 30 -vf scale=1920:1080 -c:a aac -b:a 192k demo/output/final_demo.mp4
```

**验证：**
```bash
ffprobe -v quiet -show_entries stream=width,height,r_frame_rate,codec_name -show_entries format=size demo/output/final_demo.mp4
# 预期：width=1920, height=1080, r_frame_rate=30/1, codec_name=h264, size < 524288000
```

### Day 6（8/22 周五）— 最终图表确认

- [ ] 确认报告中所有图表为最终版（数据正确、中文正常）
- [ ] 确认 PPT 中所有图表为最终版
- [ ] 确认图表文件已放入仓库 `demo/assets/charts/`
- [ ] 整理 `demo/` 目录最终状态

**验证：**
```bash
dir demo\assets\charts\report\ | find /c ".png"
# 预期：>= 10
dir demo\assets\charts\ppt\ | find /c ".png"
# 预期：>= 5
```

### Day 7（8/23 周六）— Buffer / 最终提交

- [ ] 最后修改（如有）
- [ ] 提交所有视觉交付物给 TL

**验证：**
```bash
dir demo\output\final_demo.mp4
# 预期：文件存在，大小 < 500MB
```

## 交付物

| 文件 | 截止日 | 验收标准 |
|------|--------|----------|
| 素材确认齐全 | 8/17 | 无缺失，所有录屏/动画/背景素材就绪 |
| 旁白录制完成 | 8/18 | 6 段旁白，音质清晰 |
| 视频粗剪 | 8/19 | 7 分钟、6 段结构、含字幕 |
| 视频精剪 | 8/20 | 根据反馈修改，含背景音乐 |
| 最终视频 | 8/21 | 1080p H.264 MP4，30fps，< 500MB |
| 图表最终确认 | 8/22 | 报告+PPT 图表齐全，数据正确 |

## 协作对接

- 与 DA 获取最终旁白稿（Day 2 前）
- 粗剪版发 TL 和 DA 预览收集反馈（Day 3 晚）
- 最终视频发 TL 确认后方可定版（Day 5）
