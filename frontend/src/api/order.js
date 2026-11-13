/** order 应用接口封装。 */
import request from '@/utils/request'

const ORDERS = '/order/sales-orders/'
const MPS = '/order/mps/'

export function fetchOrders(params) { return request.get(ORDERS, { params }) }
export function fetchOrder(id) { return request.get(`${ORDERS}${id}/`) }
export function createOrder(data) { return request.post(ORDERS, data) }
export function patchOrder(id, data) { return request.patch(`${ORDERS}${id}/`, data) }
export function confirmOrder(id) { return request.post(`${ORDERS}${id}/confirm/`) }
export function cancelOrder(id, data) { return request.post(`${ORDERS}${id}/cancel/`, data) }
export function fetchOrderItems(id) { return request.get(`${ORDERS}${id}/items/`) }
export function addOrderItem(id, data) { return request.post(`${ORDERS}${id}/items/`, data) }

export function fetchMpsList(params) { return request.get(MPS, { params }) }
export function fetchMps(id) { return request.get(`${MPS}${id}/`) }
export function mpsFromOrders(data) { return request.post(`${MPS}from-orders/`, data) }
export function checkKit(id) { return request.post(`${MPS}${id}/check-kit/`) }
export function fetchForecasts(params) { return request.get('/order/forecasts/', { params }) }
export function runForecast(data) { return request.post('/order/forecasts/run/', data) }
