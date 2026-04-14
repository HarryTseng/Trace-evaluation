import json
import os

def analyze_traces(file_path):
    if not os.path.exists(file_path):
        return f"錯誤：找不到檔案 '{file_path}'"

    unique_trace_ids = set()
    error_trace_ids = set()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                
                try:
                    data = json.loads(line)
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
                                
                                if code == 2 or code == "STATUS_CODE_ERROR":
                                    error_trace_ids.add(trace_id)
                                    
                except json.JSONDecodeError:
                    continue
        
        return {
            "total_traces": len(unique_trace_ids),
            "error_traces": len(error_trace_ids),
            "error_rate": (len(error_trace_ids) / len(unique_trace_ids) * 100) if unique_trace_ids else 0
        }

    except Exception as e:
        return f"發生未知錯誤：{e}"

file_name = 'traces.json'
result = analyze_traces(file_name)

if isinstance(result, dict):
    print(f"分析結果：")
    print(f"- 總 Trace 數量: {result['total_traces']}")
    print(f"- 錯誤 (Error) Trace 數量: {result['error_traces']}")
    print(f"- 錯誤率: {result['error_rate']:.2f}%")
else:
    print(result)