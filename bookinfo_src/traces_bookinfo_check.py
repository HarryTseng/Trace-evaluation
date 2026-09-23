import json
import os

def analyze_traces(file_path):
    if not os.path.exists(file_path):
        return f"錯誤：找不到檔案 '{file_path}'"

    unique_trace_ids = set()
    error_trace_ids = set()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 使用 raw_decode 兼顧多行 JSON 與 JSONL 格式，並避免結尾截斷問題
        decoder = json.JSONDecoder()
        idx = 0
        length = len(content)

        while idx < length:
            while idx < length and content[idx].isspace():
                idx += 1
            if idx >= length:
                break

            try:
                data, end = decoder.raw_decode(content, idx)
                idx = end
            except json.JSONDecodeError:
                break  # 遇到不完整或格式毀損的結尾時安全退出

            resource_spans = data.get('resourceSpans', []) if isinstance(data, dict) else []

            for resource_span in resource_spans:
                for scope_span in resource_span.get('scopeSpans', []):
                    for span in scope_span.get('spans', []):
                        trace_id = span.get('traceId')
                        if not trace_id:
                            continue

                        unique_trace_ids.add(trace_id)

                        # 只以「根 span」(沒有 parentSpanId，也就是使用者實際收到的
                        # 最終結果，例如 productpage 這一筆) 來判斷該 trace 是否為錯誤。
                        # 若只要 trace 中任何一個 span 出現 status.code=2 就算錯誤，
                        # 會把「內部重試後成功」的 trace 也誤算進去，導致錯誤數偏高。
                        if span.get('parentSpanId'):
                            continue

                        status = span.get('status', {})
                        code = status.get('code')
                        is_error_status = (code == 2 or code == "STATUS_CODE_ERROR")

                        attributes = span.get('attributes', [])
                        has_error_attr = any(
                            attr.get('key') == 'error.msg' for attr in attributes if isinstance(attr, dict)
                        )

                        if is_error_status or has_error_attr:
                            error_trace_ids.add(trace_id)

        return {
            "total_traces": len(unique_trace_ids),
            "error_traces": len(error_trace_ids),
            "error_rate": (len(error_trace_ids) / len(unique_trace_ids) * 100) if unique_trace_ids else 0
        }

    except Exception as e:
        return f"發生未知錯誤：{e}"

if __name__ == "__main__":
    file_name = 'traces_bookinfo.json'
    result = analyze_traces(file_name)

    if isinstance(result, dict):
        print("分析結果：")
        print(f"- 總 Trace 數量: {result['total_traces']}")
        print(f"- 錯誤 (Error) Trace 數量: {result['error_traces']}")
        print(f"- 錯誤率: {result['error_rate']:.2f}%")
    else:
        print(result)