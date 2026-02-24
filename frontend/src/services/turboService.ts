import axios from 'axios';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * Maps to backend TurboRunConfig (dataclass)
 */
export interface TurboConfig {
  test_case_id: string;   // 关联 API 用例
  users: number;          // 并发数
  spawn_rate: number;     // 孵化率
  duration: string;       // 持续时间
}

/**
 * Maps to backend TurboTestStats (dataclass)
 * Backend fields: test_id, state, users, total_requests, total_failures, current_rps, fail_ratio, avg_response_time, p95_response_time
 */
export interface TurboStats {
  test_id: string;
  state: string;           // "running" | "stopped" | "failed"
  users: number;
  total_requests: number;
  total_failures: number;
  current_rps: number;
  fail_ratio: number;
  avg_response_time: number;
  p95_response_time: number;
}

export const turboService = {
  /**
   * Start a stress test — POST /api/v1/turbo/run
   * Returns { test_id: string, status: "started" }
   */
  startStressTest: async (config: TurboConfig) => {
    try {
      const payload = {
        test_case_id: config.test_case_id,
        users: config.users,
        spawn_rate: config.spawn_rate,
        run_time: config.duration // backend uses run_time
      };
      const response = await axios.post(`${API_BASE_URL}/api/v1/turbo/run`, payload);
      return response.data;
    } catch (e: any) {
      console.warn("Backend turbo/run failed", e.response?.data || e.message);
      throw e;
    }
  },

  /**
   * Stop a running stress test — POST /api/v1/turbo/stop/{test_id}
   * Returns { test_id: string, status: "stopped" }
   */
  stopStressTest: async (testId: string) => {
    try {
      const response = await axios.post(`${API_BASE_URL}/api/v1/turbo/stop/${testId}`);
      return response.data;
    } catch (e) {
      console.warn("Backend turbo/stop failed");
      return { test_id: testId, status: "stopped" };
    }
  },

  /**
   * Get real-time stats — GET /api/v1/turbo/stats/{test_id}
   * Returns TurboTestStats or null
   */
  getTestStats: async (testId: string): Promise<TurboStats> => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/v1/turbo/stats/${testId}`);
      if (response.data) {
        return response.data;
      }
    } catch (e) {
      console.warn("Failed to fetch real stats");
    }
    return {
      test_id: testId,
      state: "failed",
      users: 0,
      total_requests: 0,
      total_failures: 0,
      current_rps: 0,
      fail_ratio: 0,
      avg_response_time: 0,
      p95_response_time: 0,
    };
  },

  /**
   * Fetch available API test cases
   * Tries real backend, falls back to mock data for UI development
   */
  getApiTestCases: async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/v1/test-cases?mode=API`);
      const items = response.data.items || [];
      const formattedItems = items.map((tc: any) => {
        const firstStep = tc.steps?.[0] || {};
        const firstStepReq = firstStep.request || firstStep;
        return {
          id: tc.id,
          name: tc.name,
          method: firstStepReq.method || "GET",
          url: firstStepReq.url || firstStepReq.target || "/"
        };
      });
      return { items: formattedItems };
    } catch (e) {
      console.warn("Using mock data for API cases since endpoint might not exist yet");
      return {
        items: [
          { id: "TC_API_001", name: "User Login API", method: "POST", url: "/api/v1/auth/login", target_host: "http://localhost:8000" },
          { id: "TC_API_002", name: "Fetch Product List", method: "GET", url: "/api/v1/products", target_host: "http://localhost:8000" },
          { id: "TC_API_003", name: "Create Order (Complex)", method: "POST", url: "/api/v1/orders", target_host: "http://localhost:8000" }
        ]
      };
    }
  }
};
