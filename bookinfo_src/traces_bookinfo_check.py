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
                break

            resource_spans = data.get('resourceSpans', []) if isinstance(data, dict) else []

            for resource_span in resource_spans:
                for scope_span in resource_span.get('scopeSpans', []):
                    for span in scope_span.get('spans', []):
                        trace_id = span.get('traceId')
                        if not trace_id:
                            continue

                        unique_trace_ids.add(trace_id)

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