# -*- coding: utf-8 -*-
"""单用户训练流水线：raw 音频 -> 切片 -> ASR 标注 -> s1+s2 训练 -> 可部署模型

用法（在 D:\\小米项目\\GPT-SoVITS 根目录，用 .venv 的 python 运行）:
  .venv\\Scripts\\python.exe train_data\\train_one.py --name 张三 --audio train_data\\raw\\张三.mp3
  .venv\\Scripts\\python.exe train_data\\train_one.py --name 张三 --s1-epochs 30 --s2-epochs 60 --stage-from prep
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GSV = ROOT / "GPT_SoVITS"
PRETRAINED = GSV / "pretrained_models"
DATA = ROOT / "train_data"
USERS = DATA / "users"
MODELS = DATA / "models"
LOGS = DATA / "logs"

BERT_DIR = PRETRAINED / "chinese-roberta-wwm-ext-large"
CNHUBERT_DIR = PRETRAINED / "chinese-hubert-base"
S2G_PRETRAIN = PRETRAINED / "gsv-v2final-pretrained" / "s2G2333k.pth"
S2D_PRETRAIN = PRETRAINED / "gsv-v2final-pretrained" / "s2D2333k.pth"
S1_PRETRAIN = PRETRAINED / "gsv-v2final-pretrained" / "s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt"
BASE_S2_JSON = GSV / "configs" / "s2.json"
BASE_S1_YAML = GSV / "configs" / "s1longer-v2.yaml"

PY = sys.executable

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def log(name, msg):
    line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
    try:
        print(line, flush=True)
    except Exception:
        pass
    with open(LOGS / ("%s.log" % name), "a", encoding="utf-8") as f:
        f.write(line + "\n")


FFMPEG_BIN = ROOT / "tools" / "ffmpeg_bin"


def run(name, cmd, cwd, env_extra=None, timeout_h=None):
    env = dict(os.environ)
    if FFMPEG_BIN.exists():
        env["PATH"] = str(FFMPEG_BIN) + os.pathsep + env.get("PATH", "")
    for p in (ROOT, GSV):
        env["PYTHONPATH"] = str(p) + os.pathsep + env.get("PYTHONPATH", "")
    if env_extra:
        env.update(env_extra)
    log(name, "RUN: %s (cwd=%s)" % (" ".join(cmd), cwd))
    t0 = time.time()
    p = subprocess.Popen(cmd, cwd=str(cwd), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         universal_newlines=True, encoding="utf-8", errors="replace")
    last = []
    while True:
        line = p.stdout.readline()
        if line:
            line = line.rstrip()
            last.append(line)
            if len(last) > 200:
                last.pop(0)
            if os.environ.get("TRAIN_VERBOSE"):
                log(name, "  | " + line)
        elif p.poll() is not None:
            break
    p.wait()
    dur = time.time() - t0
    if p.returncode != 0:
        log(name, "FAILED after %.1fs, rc=%s" % (dur, p.returncode))
        for l in last[-40:]:
            log(name, "  | " + l)
        raise RuntimeError("step failed: %s" % cmd[0])
    log(name, "OK in %.1fs" % dur)


def prep_envs(user_dir, sliced, list_file):
    opt = user_dir / "opt"
    return {
        "inp_text": str(list_file),
        "inp_wav_dir": str(sliced),
        "exp_name": user_dir.name,
        "i_part": "0",
        "all_parts": "1",
        "opt_dir": str(opt),
        "bert_pretrained_dir": str(BERT_DIR),
        "cnhubert_base_dir": str(CNHUBERT_DIR),
        "pretrained_s2G": str(S2G_PRETRAIN),
        "s2config_path": str(BASE_S2_JSON),
        "version": "v2",
        "is_half": "False",
    }


def ascii_str(s):
    """JSON escape (ASCII, no outer quotes); yaml double-quoted values restore via \\uXXXX"""
    return json.dumps(str(s))[1:-1]


def build_s1_yaml(user_dir, epochs):
    import yaml
    with open(BASE_S1_YAML, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    opt = user_dir / "opt"
    out_dir = user_dir / "s1"
    half_dir = out_dir / "half_weights"
    cfg["output_dir"] = str(out_dir)
    cfg["train_semantic_path"] = str(opt / "6-name2semantic-0.tsv")
    cfg["train_phoneme_path"] = str(opt / "2-name2text-0.txt")
    cfg["pretrained_s1"] = str(S1_PRETRAIN)
    cfg["train"]["epochs"] = int(epochs)
    cfg["train"]["batch_size"] = 4
    cfg["train"]["save_every_n_epoch"] = 1
    cfg["train"]["if_save_latest"] = True
    cfg["train"]["if_save_every_weights"] = True
    cfg["train"]["half_weights_save_dir"] = str(half_dir)
    cfg["train"]["exp_name"] = user_dir.name
    cfg["data"]["max_sec"] = 40
    cfg["data"]["num_workers"] = 2
    yaml_path = user_dir / "s1.yaml"
    with open(yaml_path, "w", encoding="gbk") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
    return yaml_path


def build_s2_json(user_dir, list_file, epochs):
    with open(BASE_S2_JSON, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    opt = user_dir / "opt"
    s2_dir = user_dir / "s2"
    ckpt_dir = s2_dir / "ckpt"
    weights_dir = s2_dir / "weights"
    cfg["name"] = user_dir.name
    cfg["model"]["version"] = "v2"
    cfg["model_dir"] = str(ckpt_dir)
    cfg["s2_ckpt_dir"] = str(ckpt_dir)
    cfg["save_weight_dir"] = str(weights_dir)
    cfg["data"]["exp_dir"] = str(opt)
    cfg["data"]["train_dataset_path"] = str(list_file)
    cfg["data"]["validation_files"] = ""
    cfg["train"]["pretrained_s2G"] = str(S2G_PRETRAIN)
    cfg["train"]["pretrained_s2D"] = str(S2D_PRETRAIN)
    cfg["train"]["epochs"] = int(epochs)
    cfg["train"]["batch_size"] = 8
    cfg["train"]["gpu_numbers"] = "0"
    cfg["train"]["if_save_latest"] = 1
    cfg["train"]["if_save_every_weights"] = True
    cfg["train"]["save_every_epoch"] = 1
    if not (opt / "2-name2text.txt").exists() and (opt / "2-name2text-0.txt").exists():
        shutil.copy(opt / "2-name2text-0.txt", opt / "2-name2text.txt")
    (opt / "logs_s2_v2").mkdir(parents=True, exist_ok=True)
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    weights_dir.mkdir(parents=True, exist_ok=True)
    json_path = user_dir / "s2.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=True, indent=2)
    return json_path


def resolve_user_dir(name):
    """返回 ASCII 工作目录（users/uN/），显示名存 meta.json，避免中文路径破坏 GSV 的 GBK 读取"""
    for d in sorted(USERS.glob("u*")):
        if d.is_dir():
            meta = d / "meta.json"
            if meta.exists():
                try:
                    if json.loads(meta.read_text(encoding="utf-8")).get("display_name") == name:
                        return d
                except Exception:
                    pass
    n = 1
    while (USERS / ("u%d" % n)).exists():
        n += 1
    d = USERS / ("u%d" % n)
    d.mkdir(parents=True)
    (d / "meta.json").write_text(json.dumps({"display_name": name}, ensure_ascii=False), encoding="utf-8")
    return d


def to_ascii_wav(audio, name):
    """把任意格式音频转成 ASCII 路径的 32k 单声道 wav（slicer 输入）"""
    work = DATA / "raw_work"
    work.mkdir(exist_ok=True)
    out = work / ("input_%s.wav" % name)
    env = dict(os.environ)
    if FFMPEG_BIN.exists():
        env["PATH"] = str(FFMPEG_BIN) + os.pathsep + env.get("PATH", "")
    subprocess.run([str(FFMPEG_BIN / "ffmpeg.exe"), "-y", "-i", str(audio), "-ar", "32000", "-ac", "1", str(out)],
                   env=env, capture_output=True, check=True)
    return out


def stop_gsv_api(name):
    """训练期间释放内存：停掉 9880 推理服务（训练完 deploy 后用户重启）"""
    try:
        import subprocess as sp
        out = sp.run(["powershell", "-NoProfile", "-Command",
                      "$c = Get-NetTCPConnection -LocalPort 9880 -State Listen -ErrorAction SilentlyContinue; if ($c) { Stop-Process -Id $c.OwningProcess -Force }"],
                     capture_output=True, timeout=30)
        log(name, "已停止 GPT-SoVITS API 服务（释放内存用于训练）")
    except Exception as e:
        log(name, "停止 GSV API 失败: %s" % e)


def train_one(name, audio, s1_epochs, s2_epochs, stage_from):
    user_dir = resolve_user_dir(name)
    sliced = user_dir / "sliced"
    asr_dir = user_dir / "asr"
    opt = user_dir / "opt"
    for d in (USERS, MODELS, LOGS, user_dir, sliced, asr_dir, opt):
        d.mkdir(parents=True, exist_ok=True)
    log(name, "=== 训练任务开始: %s  audio=%s  s1=%s  s2=%s  work=%s ===" % (name, audio, s1_epochs, s2_epochs, user_dir))

    stages = ["slice", "asr", "prep", "s2", "s1", "deploy"]
    if stage_from in stages:
        stages = stages[stages.index(stage_from):]

    def _find_list():
        lists = sorted(asr_dir.glob("*.list"))
        if not lists:
            raise RuntimeError("ASR 输出缺失（asr 目录无 .list）")
        return lists[0]

    list_file = None
    if asr_dir.exists():
        try:
            list_file = _find_list()
        except RuntimeError:
            list_file = None

    if any(s in stages for s in ("s2", "s1")):
        stop_gsv_api(name)

    if "slice" in stages:
        wav = to_ascii_wav(audio, user_dir.name)
        run(name, [PY, "-c",
                   "import sys; sys.path.insert(0, 'tools'); sys.argv[1:] = [%r, %r, '-40', '3000', '250', '10', '350', '0.9', '0.25', '0', '1']; from tools.slice_audio import slice" % (str(wav), str(sliced))],
            cwd=ROOT)
        n_slices = len(list(sliced.glob("*.wav")))
        if n_slices < 3:
            raise RuntimeError("切片过少(%d段)，请提供 1~3 分钟清晰录音" % n_slices)
        log(name, "切片完成: %d 段" % n_slices)

    if "asr" in stages:
        run(name, [PY, str(ROOT / "tools" / "asr" / "funasr_asr.py"),
                   "-i", str(sliced), "-o", str(asr_dir), "-l", "zh"], cwd=ROOT)
        list_file = _find_list()
        n = sum(1 for _ in open(list_file, encoding="utf-8"))
        log(name, "ASR 完成: %d 条标注" % n)
    elif list_file is None:
        list_file = _find_list()

    if "prep" in stages:
        env = prep_envs(user_dir, sliced, list_file)
        run(name, [PY, str(GSV / "prepare_datasets" / "1-get-text.py")], cwd=ROOT, env_extra=env)
        run(name, [PY, str(GSV / "prepare_datasets" / "2-get-hubert-wav32k.py")], cwd=ROOT, env_extra=env)
        run(name, [PY, str(GSV / "prepare_datasets" / "3-get-semantic.py")], cwd=ROOT, env_extra=env)
        for p in ("2-name2text-0.txt", "6-name2semantic-0.tsv"):
            if not (opt / p).exists():
                raise RuntimeError("数据准备缺失: %s" % p)
        log(name, "数据准备完成 (phoneme/semantic/bert/hubert)")

    if "s2" in stages:
        s2_json = build_s2_json(user_dir, list_file, s2_epochs)
        run(name, [PY, str(GSV / "s2_train.py"), "-c", str(s2_json)], cwd=GSV, timeout_h=12)
        savee_s2(name, user_dir, s2_json, s2_epochs)

    if "s1" in stages:
        s1_yaml = build_s1_yaml(user_dir, s1_epochs)
        run(name, [PY, str(GSV / "s1_train.py"), "-c", str(s1_yaml)], cwd=GSV, timeout_h=12)

    if "deploy" in stages:
        deploy(name, user_dir)
    log(name, "=== 训练完成: %s ===" % name)


def savee_s2(name, user_dir, s2_json, epochs):
    """s2 训练产物 → s2G.pth（半精度 + config，推理直接加载）"""
    opt = user_dir / "opt"
    ckpts = sorted((opt / "logs_s2_v2").glob("G_*.pth"))
    if not ckpts:
        raise RuntimeError("未找到 s2 训练 checkpoint (opt/logs_s2_v2/G_*.pth)")
    ckpt_path = ckpts[-1]
    weights_dir = user_dir / "s2" / "weights"
    weights_dir.mkdir(parents=True, exist_ok=True)
    script = (
        "import sys, torch\n"
        "sys.path.insert(0, %r)\n"
        "from GPT_SoVITS.process_ckpt import savee\n"
        "import GPT_SoVITS.utils as utils\n"
        "hps = utils.get_hparams_from_file(%r)\n"
        "ck = torch.load(%r, map_location='cpu')\n"
        "steps = int(ck.get('iteration', 0)) if isinstance(ck, dict) else 0\n"
        "ck = ck['model'] if isinstance(ck, dict) and 'model' in ck else ck\n"
        "print(savee(ck, 's2G', %d, steps, hps))\n"
    ) % (str(ROOT), str(s2_json), str(ckpt_path), int(epochs))
    run(name, [PY, "-c", script], cwd=GSV)
    out = weights_dir / "s2G.pth"
    if not out.exists():
        raise RuntimeError("savee 失败，未生成 %s" % out)
    log(name, "s2 转换完成: %s" % out)


def deploy(name, user_dir):
    out = MODELS / user_dir.name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    s2_weights_dir = user_dir / "s2" / "weights"
    if not any(s2_weights_dir.glob("*.pth")):
        s2_json = user_dir / "s2.json"
        if not s2_json.exists():
            raise RuntimeError("缺少 s2.json，无法转换 s2 权重")
        savee_s2(name, user_dir, s2_json, 0)
    ckpts = sorted((user_dir / "s1" / "half_weights").glob("%s-e*.ckpt" % name))
    if not ckpts:
        raise RuntimeError("未找到 s1 训练产物 %s-e*.ckpt" % name)
    s1_ckpt = ckpts[-1]
    s2_ckpts = sorted((user_dir / "s2" / "weights").glob("*.pth")) or sorted((user_dir / "s2" / "ckpt").glob("*.pth"))
    if not s2_ckpts:
        raise RuntimeError("未找到 s2 训练产物")
    s2_pth = [p for p in s2_ckpts if p.name.startswith("s2G")][-1] if any(
        p.name.startswith("s2G") for p in s2_ckpts) else s2_ckpts[-1]
    shutil.copy(s1_ckpt, out / "s1.ckpt")
    shutil.copy(s2_pth, out / "s2G.pth")
    refs = sorted((user_dir / "opt" / "5-wav32k").glob("*.wav")) if (user_dir / "opt" / "5-wav32k").exists() \
        else sorted((user_dir / "sliced").glob("*.wav"))
    ref = None
    for r in refs:
        sz = r.stat().st_size
        if 30000 < sz < 400000:
            ref = r
            break
    if ref is None and refs:
        ref = refs[0]
    if ref is None:
        raise RuntimeError("无参考音频")
    shutil.copy(ref, out / "ref.wav")
    txt_path = user_dir / "opt" / "2-name2text-0.txt"
    ref_text = ""
    if txt_path.exists():
        base = ref.stem
        for line in open(txt_path, encoding="utf-8"):
            if line.startswith(base + "\t") or line.startswith(base + "."):
                parts = line.rstrip("\n").split("\t")
                ref_text = parts[3] if len(parts) > 3 else parts[1]
                break
    (out / "ref.txt").write_text(ref_text, encoding="utf-8")
    manifest = {
        "name": user_dir.name,
        "display_name": name,
        "s1": "s1.ckpt",
        "s2": "s2G.pth",
        "ref": "ref.wav",
        "ref_text": ref_text,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    log(name, "模型已部署: %s" % out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--audio", required=True, help="raw 音频路径 (wav/mp3)")
    ap.add_argument("--s1-epochs", type=int, default=20)
    ap.add_argument("--s2-epochs", type=int, default=50)
    ap.add_argument("--stage-from", choices=["slice", "asr", "prep", "s2", "s1", "deploy"], default="slice",
                    help="从某阶段开始（用于断点续跑）")
    a = ap.parse_args()
    try:
        train_one(a.name, Path(a.audio).resolve(), a.s1_epochs, a.s2_epochs, a.stage_from)
    except Exception:
        import traceback
        tb = traceback.format_exc()
        with open(LOGS / ("%s.log" % a.name), "a", encoding="utf-8") as f:
            f.write("[%s] 主进程异常:\n%s\n" % (time.strftime("%H:%M:%S"), tb))
        try:
            print(tb, file=sys.stderr)
        except Exception:
            pass
        sys.exit(1)
