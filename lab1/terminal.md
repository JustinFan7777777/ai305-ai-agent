# 练习 1：体验终端中的文本交互

在解压后的 `lab1/code/` 目录（包含 `pyproject.toml`）中，按顺序逐条执行下面的命令，观察输入和结果。
命令已经提供。

## 查看文件

```sh
pwd
ls workspace/
find workspace/ -name project.txt
head -n 3 workspace/README.md
grep ERROR workspace/records/session.txt
```

观察：输入包含命令和参数，终端显示目录、路径或文件内容。

## 查看正常输出和错误

```sh
head -n 3 workspace/README.md
echo $?
head workspace/missing.txt
echo $?
```

前一次读取成功，退出状态为 0。后一次文件不存在，会显示错误并返回非零状态。
`echo $?` 要紧接目标命令执行，它显示的是上一条命令的退出状态。

## 保存结果

下面的命令会创建 `submission/`，复制文件并保存输出。

```sh
mkdir -p submission/project submission/results
cp workspace/config/project.txt submission/project/project.txt
head -n 3 workspace/README.md > submission/results/preview.txt
grep ERROR workspace/records/session.txt > submission/results/errors.txt
cat submission/results/preview.txt
cat submission/results/errors.txt
```

观察：`>` 把正常输出写入文件，`cat` 再将保存的内容显示到终端。

## 运行检查

```sh
uv run python lab1_check.py
```

全部显示 PASS 即通过。检查脚本只读取目录和文件，不修改结果。
