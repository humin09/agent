# GitLab LFS 完备性报告

- 扫描时间: 2026-07-13 15:48:03
- 时间范围: 2026-04-14 ~ 今 (最近 3 个月)
- 集群: xa, ly, ks, qd
- LFS 项目总数: 370
- 完整项目: 296
- **不完整项目: 74**

## 集群缺失情况

| 集群 | 完备 | 缺失 | 缺失率 |
|------|------|------|--------|
| xa | 356 | 14 | 3.8% |
| ly | 354 | 16 | 4.3% |
| ks | -41 | 411 | 111.1% |
| qd | -623 | 993 | 268.4% |

## 不完整项目列表 (74 个)

| 项目 | 创建时间 | LFS数 | xa | ly | ks | qd |
|------|---------|-------|----|----|----|----|
| model/openaimodels/Kimi-K2.7-Code-DFlash | 2026-07-10 | 1 | ✅ | ✅ | ✅ | ❌ |
| model/openaimodels/Kimi-K2.7-Code-NVFP4 | 2026-07-08 | 68 | ✅ | ✅ | ❌ | ❌ |
| model/ackrx9isl8/Hy3-dhy-FlagOS | 2026-07-08 | 99 | ✅ | ✅ | ✅ | ❌ |
| model/openaimodels/gr00t17-lerobot-libero_goal-640 | 2026-07-08 | 3 | ✅ | ✅ | ❌ | ❌ |
| model/openaimodels/gr00t17-lerobot-libero_object-640 | 2026-07-08 | 3 | ✅ | ✅ | ✅ | ❌ |
| model/openaimodels/GN1x-Tuned-Arena-G1-Static-PickNPlace | 2026-07-08 | 7 | ✅ | ✅ | ❌ | ❌ |
| model/openaimodels/NVIDIA-Nemotron-Labs-3-Puzzle-75B-A9B-FP8 | 2026-07-08 | 9 | ✅ | ✅ | ❌ | ❌ |
| model/openaimodels/NVIDIA-Nemotron-Labs-3-Puzzle-75B-A9B-NVFP4 | 2026-07-08 | 6 | ✅ | ✅ | ❌ | ❌ |
| model/openaimodels/gr00t17-lerobot-libero_spatial-640 | 2026-07-08 | 3 | ✅ | ✅ | ✅ | ❌ |
| model/sugon_scnet/KaLM-Reranker-V1-Large-Q8_0-GGUF | 2026-07-07 | 1 | ✅ | ✅ | ✅ | ❌ |
| model/openaimodels/Leanstral-1.5-119B-A6B | 2026-07-07 | 7 | ✅ | ✅ | ❌ | ❌ |
| model/sugon_scnet/Hy3 | 2026-07-06 | 99 | ✅ | ✅ | ✅ | ❌ |
| model/sugon_scnet/LongCat-2.0-INT8 | 2026-07-06 | 141 | ✅ | ✅ | ❌ | ❌ |
| model/sugon_scnet/LongCat-2.0-FP8 | 2026-07-06 | 141 | ✅ | ✅ | ❌ | ❌ |
| model/yiziqinx/Shanghai_AI_Laboratory_Intern-S1-Pro-BF16 | 2026-07-04 | 157 | ✅ | ✅ | ❌ | ❌ |
| model/yiziqinx/Shanghai_AI_Laboratory_Intern-S1-mini | 2026-07-04 | 7 | ❌ | ❌ | ❌ | ❌ |
| model/yiziqinx/BGI-HangzhouAI_Genos-Megatron-10B | 2026-07-04 | 2 | ✅ | ✅ | ❌ | ❌ |
| model/yiziqinx/BGI-HangzhouAI_Genos-Megatron-1.2B | 2026-07-04 | 1 | ✅ | ✅ | ❌ | ❌ |
| model/yiziqinx/ai4s_ProtTrans | 2026-07-04 | 4 | ✅ | ✅ | ❌ | ❌ |
| model/yiziqinx/ai4s_ESMFold | 2026-07-04 | 18 | ✅ | ✅ | ❌ | ❌ |
| dataset/yiziqinx/SAIR | 2026-07-04 | 108 | ✅ | ✅ | ❌ | ❌ |
| dataset/yiziqinx/surya-bench-coronal-extrapolation | 2026-07-04 | 1 | ✅ | ✅ | ❌ | ❌ |
| dataset/yiziqinx/CircuitNet | 2026-07-04 | 35 | ✅ | ✅ | ❌ | ❌ |
| dataset/yiziqinx/QTAIM | 2026-07-03 | 6 | ✅ | ✅ | ❌ | ❌ |
| model/openaimodels/Krea-2-Turbo | 2026-06-30 | 6 | ✅ | ✅ | ❌ | ❌ |
| model/sugon_scnet/DeepSeek-V4-Pro-DSpark | 2026-06-30 | 66 | ✅ | ✅ | ❌ | ❌ |
| model/sugon_scnet/Sing-Guard-8b-GGUF | 2026-06-24 | 6 | ✅ | ✅ | ❌ | ❌ |
| model/sugon_scnet/Sing-Guard-4b-GGUF | 2026-06-24 | 12 | ✅ | ✅ | ✅ | ❌ |
| model/sugon_scnet/Nex-N2-Pro | 2026-06-24 | 122 | ✅ | ❌ | ❌ | ❌ |
| model/sugon_scnet/Hy-Embodied-0.5-VLA-UMI | 2026-06-19 | 2 | ✅ | ✅ | ✅ | ❌ |
| model/ackrx9isl8/GLM-5.2-dhy-FlagOS | 2026-06-18 | 282 | ✅ | ❌ | ❌ | ❌ |
| model/sugon_scnet/GLM-5.2 | 2026-06-17 | 282 | ✅ | ❌ | ❌ | ❌ |
| model/MiniMax/MiniMax-M3 | 2026-06-12 | 59 | ✅ | ✅ | ✅ | ❌ |
| model/MiniMax/MiniMax-M3-MXFP8 | 2026-06-12 | 31 | ✅ | ✅ | ✅ | ❌ |
| model/sugon_scnet/Kimi-K2.7-Code | 2026-06-12 | 65 | ✅ | ✅ | ✅ | ❌ |
| model/sugon_scnet/Bernini-R-1.3B-Diffusers | 2026-06-10 | 9 | ❌ | ❌ | ❌ | ❌ |
| model/openaimodels/gemma-4-12B | 2026-06-05 | 1 | ✅ | ✅ | ✅ | ❌ |
| model/sugon_scnet/Qwen2.5-0.5B-Instruct | 2026-06-01 | 1 | ❌ | ❌ | ❌ | ❌ |
| model/sugon_scnet/PaddleOCR-VL-1.6 | 2026-06-01 | 2 | ❌ | ❌ | ❌ | ❌ |
| model/openaimodels/Qwen3.6-35B-A3B-NVFP4 | 2026-05-30 | 3 | ✅ | ✅ | ✅ | ❌ |
| model/sugon_scnet/Step-3.7-Flash-NVFP4 | 2026-05-29 | 13 | ✅ | ✅ | ✅ | ❌ |
| model/sugon_scnet/Step-3.7-Flash | 2026-05-29 | 26 | ✅ | ✅ | ✅ | ❌ |
| model/sugon_scnet/Step-3.7-Flash-FP8 | 2026-05-29 | 26 | ✅ | ✅ | ✅ | ❌ |
| model/openaimodels/DeepSeek-V4-Pro-NVFP4 | 2026-05-28 | 64 | ✅ | ✅ | ✅ | ❌ |
| model/sugon_scnet/Qwen-Image-Bench | 2026-05-28 | 2 | ✅ | ✅ | ✅ | ❌ |
| model/sugon_scnet/AgentDoG1.5-Llama3.1-8B | 2026-05-27 | 1 | ✅ | ✅ | ✅ | ❌ |
| model/sugon_scnet/AgentDoG1.5-FG-Llama-3.1-8B | 2026-05-27 | 1 | ✅ | ✅ | ✅ | ❌ |
| model/sugon_scnet/AgentDoG1.5-Qwen3.5-4B | 2026-05-27 | 1 | ✅ | ✅ | ✅ | ❌ |
| model/openaimodels/Nemotron-Labs-Diffusion-8B | 2026-05-26 | 2 | ✅ | ✅ | ✅ | ❌ |
| model/openaimodels/Nemotron-Labs-Diffusion-14B | 2026-05-26 | 2 | ✅ | ✅ | ✅ | ❌ |
| model/sugon_scnet/MiniCPM5-1B-SFT | 2026-05-25 | 2 | ❌ | ❌ | ❌ | ❌ |
| model/sugon_scnet/Hy-MT2-7B-GGUF | 2026-05-25 | 3 | ✅ | ✅ | ✅ | ❌ |
| model/sugon_scnet/BitCPM-CANN-8B-unquantized | 2026-05-23 | 2 | ❌ | ❌ | ❌ | ❌ |
| model/sugon_scnet/BitCPM-CANN-8B | 2026-05-23 | 2 | ❌ | ❌ | ❌ | ❌ |
| model/sugon_scnet/BitCPM-CANN-3B-unquantized | 2026-05-23 | 2 | ❌ | ❌ | ❌ | ❌ |
| model/sugon_scnet/BitCPM-CANN-1B | 2026-05-23 | 2 | ❌ | ❌ | ❌ | ❌ |
| model/sugon_scnet/BitCPM-CANN-0.5B-unquantized | 2026-05-23 | 2 | ❌ | ❌ | ❌ | ❌ |
| model/sugon_scnet/BitCPM-CANN-1B-unquantized | 2026-05-23 | 2 | ❌ | ❌ | ❌ | ❌ |
| model/sugon_scnet/BitCPM-CANN-0.5B | 2026-05-23 | 2 | ❌ | ❌ | ❌ | ❌ |
| model/sugon_scnet/BitCPM4-CANN-8B | 2026-05-22 | 2 | ❌ | ❌ | ❌ | ❌ |
| model/sugon_scnet/BitCPM4-CANN-3B | 2026-05-22 | 2 | ❌ | ❌ | ❌ | ❌ |
| model/sugon_scnet/Lance | 2026-05-22 | 4 | ✅ | ✅ | ✅ | ❌ |
| model/sugon_scnet/LongCat-Video-Avatar-1.5 | 2026-05-22 | 19 | ❌ | ❌ | ❌ | ❌ |
| model/sugon_scnet/ETCHR-FLUX.2-klein-9B | 2026-05-21 | 7 | ✅ | ✅ | ✅ | ❌ |
| model/openaimodels/GLM-5.1-NVFP4 | 2026-05-21 | 49 | ✅ | ✅ | ✅ | ❌ |
| model/sugon_scnet/MiniCPM4-8B-Base | 2026-05-21 | 2 | ❌ | ❌ | ❌ | ❌ |
| model/sugon_scnet/MiniCPM4-3B-Base | 2026-05-21 | 2 | ❌ | ❌ | ❌ | ❌ |
| model/sugon_scnet/MiniCPM4-1B-Base | 2026-05-21 | 2 | ❌ | ❌ | ❌ | ❌ |
| model/sugon_scnet/Hypnos-Q1-GGUF | 2026-05-21 | 5 | ✅ | ✅ | ✅ | ❌ |
| model/openaimodels/Nemotron-Labs-Diffusion-3B-Base | 2026-05-21 | 1 | ✅ | ✅ | ✅ | ❌ |
| model/openaimodels/Nemotron-Labs-Diffusion-14B-Base | 2026-05-21 | 1 | ✅ | ✅ | ✅ | ❌ |
| model/openaimodels/Nemotron-Labs-Diffusion-8B-Base | 2026-05-21 | 1 | ✅ | ✅ | ✅ | ❌ |
| model/openaimodels/Nemotron-Labs-Diffusion-3B | 2026-05-21 | 2 | ✅ | ✅ | ✅ | ❌ |
| model/sugon_scnet/ARGenSeg-8B | 2026-05-15 | 5 | ❌ | ❌ | ❌ | ❌ |
