import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  // 設定 50 個虛擬用戶同時在線上
  vus: 10, 
  // 測試持續時間
  duration: '10s', 
};

export default function () {
  const url = 'http://localhost:8000/hello';
  
  // 發送 GET 請求
  const res = http.get(url);

  // 基本檢查：是否為 200 OK
  check(res, {
    'is status 200': (r) => r.status === 200,
  });

  // 如果你想模擬更真實的行為，可以加一點點間隔（例如 0.1 秒）
  // 如果要衝極限 Throughput，就把下面這行註解掉
  // sleep(0.1);
}