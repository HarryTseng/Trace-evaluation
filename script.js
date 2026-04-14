import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 10,
  duration: '30s',
  thresholds: {
    http_req_failed: ['rate<1.0'],
  },
};

export default function () {
  const res = http.get('http://localhost:8000/hello');
  
  check(res, {
    'is status 200': (r) => r.status === 200,
  });

  sleep(0.1);
}