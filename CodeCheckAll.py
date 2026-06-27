import os
import sys
import subprocess
import datetime
# sys.path.append("./")
# from Utils import Log
from openai import OpenAI
import difflib


MAX_DIFF_SIZE = 5000000  # 默认buffer大小5MB
checkDir = "./"         # 默认目录 自己配置
outfile = "code-review-report"
client = OpenAI(
    api_key='sk-t-j0fTpLSn4clWYu2am0pQ',
    base_url="http://10.49.3.5:8080")

useModel="auto"		# deepseek-v4-flash

# Anthropic：
# url:http://10.49.3.5:8080
# api_key:sk-t-j0fTpLSn4clWYu2am0pQ

# OpenAI:
# url:http://10.49.3.5:8080/v1
# api_key:sk-t-j0fTpLSn4clWYu2am0pQ

# "model": "auto"




# 审查规则（统一规范）
REVIEW_PROMPT = """
你是资深代码审查专家,请审查以下提供的完整代码。

审查维度：
1. 语法错误、逻辑错误、边界条件
2. 空指针、内存泄漏、未处理异常
3. 代码规范:命名、注释、格式、圈复杂度
4. 安全风险:硬编码密钥、注入、越权
5. 性能问题:冗余计算、无效循环、阻塞IO
6. 业务逻辑正确性
7. 线程安全：共享数据是否有锁，有无死锁风险
8. 内存分配：频繁new/malloc的地方是否配对delete/free
9. 文件/网络操作：是否有超时机制、异常处理
10. 事件队列：是否有最大长度限制，防止积压
11. 单例/全局变量：是否被多线程正确保护
12. 向量/数组调用：是否判断index合法性


输出格式必须严格如下，不要额外解释：
【审查结论】通过 / 需修改
【问题数量】x
【问题1】文件:行号：描述 | 等级：高/中/低 | 修复建议:xxx
【问题2】...
"""


def get_directory_code(directory):
    """获取目录下所有代码文件的内容"""
    # 支持的代码文件类型
    CODE_EXTENSIONS = ['.py', '.c', '.h', '.cpp', '.hpp', '.java', '.js', '.ts', '.cs', '.go']
    
    # 忽略的目录
    IGNORE_DIRS = ['.git', '__pycache__', 'venv', 'node_modules', '.vscode', 'build', 'dist']
    
    code_content = []
    total_size = 0
    
    def should_ignore(path):
        for ignore_dir in IGNORE_DIRS:
            # 使用os.path.sep处理路径分隔符，避免反斜杠转义问题
            if f"{os.path.sep}{ignore_dir}{os.path.sep}" in path or path.endswith(f"{os.path.sep}{ignore_dir}"):
                return True
        return False
    
    for root, dirs, files in os.walk(directory):
        # 过滤要忽略的目录
        dirs[:] = [d for d in dirs if not should_ignore(os.path.join(root, d))]
        
        for file in files:
            file_path = os.path.join(root, file)
            file_ext = os.path.splitext(file)[1].lower()
            
            if file_ext in CODE_EXTENSIONS:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # 计算相对路径
                    relative_path = os.path.relpath(file_path, directory)
                    
                    # 限制单个文件大小
                    MAX_FILE_SIZE = 100000  # 100KB
                    if len(content) > MAX_FILE_SIZE:
                        content = content[:MAX_FILE_SIZE] + "\n...[文件内容已截断]..."
                    
                    # 构建文件内容块
                    file_block = f"=== 文件: {relative_path} ===\n"
                    file_block += content + "\n\n"
                    
                    # 检查总大小
                    block_size = len(file_block)
                    if total_size + block_size > MAX_DIFF_SIZE:
                        # 计算剩余空间
                        remaining = MAX_DIFF_SIZE - total_size
                        if remaining > 0:
                            code_content.append(file_block[:remaining] + "\n...[总内容已截断]...")
                        break
                    
                    code_content.append(file_block)
                    total_size += block_size
                    
                except Exception as e:
                    print(f"读取文件失败 {file_path}: {e}")
        
        if total_size >= MAX_DIFF_SIZE:
            break
    
    return ''.join(code_content)
	


def get_git_diff(_pwd):
    """获取当前未提交的代码改动"""
    # print("dir: " + _pwd)
    try:
        # git diff > changes.patch
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=_pwd,
            capture_output=True,
            text=True,
            encoding="utf-8"
        )
        return result.stdout.strip()
    except:
        print("no diff")
        return ""
def ai_review(code_content):

    if not code_content:
        return "【审查结论】通过\n【问题数量】0\n无代码内容"
    
    # 限制代码大小，避免超出模型上下文窗口
    if len(code_content) > MAX_DIFF_SIZE:
        print(f"代码内容过大({len(code_content)}字符)，已截断为{MAX_DIFF_SIZE}字符")
        code_content = code_content[:MAX_DIFF_SIZE] + "\n...[内容已截断]..."
    
    try:
        response = client.chat.completions.create(
            model=useModel,		# deepseek-v4-flash
            messages=[
                {"role": "system", "content": REVIEW_PROMPT},
                {"role": "user", "content": f"代码内容:\n{code_content}"}
            ],
            stream=False,
            reasoning_effort="high",
            extra_body={"thinking": {"type": "enabled"}}
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"AI审查失败: {e}")
        return f"【审查结论】失败\n【问题数量】0\nAI审查接口调用失败: {e}"
    
def main():
    checkpwd = checkDir
    if (sys.argv.__len__() > 1 and isinstance(sys.argv[1], str)):
        checkpwd = sys.argv[1]
        print("checkpwd: " + checkpwd)
    
    print(f"正在收集目录 {checkpwd} 下的所有代码文件...")
    code_content = get_directory_code(checkpwd)
    
    print(f"收集完成，总代码量: {len(code_content)} 字符, 大模型审查中...")
    report = "【审查时间】 " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n" + ai_review(code_content)
    print(report)
    
    filename = outfile+"-"+datetime.datetime.now().strftime("%Y-%m-%d-%H_%M_%S") + ".txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n报告已保存至 {filename}")
if __name__ == '__main__':
    main()