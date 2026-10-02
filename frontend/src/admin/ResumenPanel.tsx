import { useEffect, useRef, useState, type MouseEvent, type ReactNode } from 'react'
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Stack,
  ToggleButton,
  ToggleButtonGroup,
  Typography,
} from '@mui/material'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useAuth } from '../auth/AuthContext'
import { chartColors } from '../theme'
import FilterBar from './FilterBar'
import KpiCard from './KpiCard'
import { fetchCategories, formatMoney, STATE_COLORS, type InventoryState } from '../api/shared'
import {
  fetchKpis,
  fetchPurchasesSummary,
  fetchSalesByCategory,
  fetchSalesTrend,
  fetchTopProducts,
  type KpisResponse,
  type TrendGroupBy,
} from './api'

export interface ResumenPanelProps {
  onStateClick: (state: InventoryState) => void
}

const STATE_ORDER: InventoryState[] = ['agotado', 'bajo', 'disponible', 'exceso']

const CATEGORY_LIMIT = 8

// --- fechas (ISO-8601 locales, YYYY-MM-DD) ---

function toIsoLocal(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function presetRange(days: number): { from: string; to: string } {
  const to = new Date()
  const from = new Date()
  from.setDate(to.getDate() - (days - 1))
  return { from: toIsoLocal(from), to: toIsoLocal(to) }
}

// Etiqueta legible para buckets 'YYYY-MM-DD' (día/semana) y 'YYYY-MM' (mes).
function formatBucket(value: string): string {
  if (/^\d{4}-\d{2}$/.test(value)) {
    const [year, month] = value.split('-')
    return `${month}/${year}`
  }
  const parts = value.split('-')
  if (parts.length === 3) return `${parts[2]}/${parts[1]}`
  return value
}

function formatAxisMoney(value: number | string): string {
  return `$${Math.round(Number(value)).toLocaleString('es-ES')}`
}

// --- carga asíncrona por dataset (loading / error independientes) ---

interface AsyncResult<T> {
  data: T | null
  loading: boolean
  error: string | null
}

// `key` identifica los parámetros de la petición ('' = sin petición); `factory`
// usa el closure del render actual y se lee vía ref, así el efecto sólo depende
// de `key`.
function useAsync<T>(key: string, factory: (() => Promise<T>) | null): AsyncResult<T> {
  const factoryRef = useRef(factory)
  useEffect(() => {
    factoryRef.current = factory
  })

  const [result, setResult] = useState<{ key: string; data: T | null; error: string | null }>({
    key: '',
    data: null,
    error: null,
  })

  useEffect(() => {
    if (key === '') return
    const current = factoryRef.current
    if (!current) return
    let active = true
    current()
      .then((data) => {
        if (active) setResult({ key, data, error: null })
      })
      .catch((err: unknown) => {
        if (active)
          setResult({
            key,
            data: null,
            error: err instanceof Error ? err.message : 'Error al cargar los datos',
          })
      })
    return () => {
      active = false
    }
  }, [key])

  const fresh = result.key === key
  return {
    data: fresh ? result.data : null,
    error: fresh ? result.error : null,
    loading: key !== '' && !fresh,
  }
}

// --- piezas de presentación ---

function LoadingCard() {
  return (
    <Card
      variant="outlined"
      sx={{ height: '100%', borderRadius: '14px', borderColor: '#E5E7EB', boxShadow: 'none' }}
    >
      <CardContent
        sx={{ minHeight: 132, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
      >
        <CircularProgress size={28} />
      </CardContent>
    </Card>
  )
}

interface ChartCardProps {
  title: string
  subtitle: string
  action?: ReactNode
  loading: boolean
  error: string | null
  empty: boolean
  height?: number
  children: ReactNode
}

function ChartCard({
  title,
  subtitle,
  action,
  loading,
  error,
  empty,
  height = 300,
  children,
}: ChartCardProps) {
  return (
    <Card
      variant="outlined"
      sx={{ height: '100%', borderRadius: '14px', borderColor: '#E5E7EB', boxShadow: 'none' }}
    >
      <CardContent>
        <Stack
          direction="row"
          spacing={1}
          sx={{ alignItems: 'flex-start', justifyContent: 'space-between' }}
        >
          <Box>
            <Typography variant="h6" sx={{ fontWeight: 600 }}>
              {title}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              {subtitle}
            </Typography>
          </Box>
          {action}
        </Stack>
        <Box
          sx={{
            mt: 2,
            height,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {loading ? (
            <CircularProgress size={32} />
          ) : error ? (
            <Alert severity="error" sx={{ width: '100%' }}>
              {error}
            </Alert>
          ) : empty ? (
            <Typography variant="body2" color="text.secondary">
              Sin datos para el período.
            </Typography>
          ) : (
            children
          )}
        </Box>
      </CardContent>
    </Card>
  )
}

function InventoryCard({
  kpis,
  loading,
  error,
  onStateClick,
}: {
  kpis: KpisResponse | null
  loading: boolean
  error: string | null
  onStateClick: (state: InventoryState) => void
}) {
  return (
    <Card
      variant="outlined"
      sx={{ borderRadius: '14px', borderColor: '#E5E7EB', boxShadow: 'none' }}
    >
      <CardContent>
        <Typography variant="h6" sx={{ fontWeight: 600 }}>
          Inventario
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Valor y estado del catálogo activo
        </Typography>

        {loading ? (
          <Box sx={{ py: 3, display: 'flex', justifyContent: 'center' }}>
            <CircularProgress size={28} />
          </Box>
        ) : error ? (
          <Alert severity="error">{error}</Alert>
        ) : kpis ? (
          <Stack
            direction={{ xs: 'column', md: 'row' }}
            spacing={{ xs: 2, md: 4 }}
            useFlexGap
            sx={{ alignItems: { md: 'center' }, flexWrap: 'wrap' }}
          >
            <Box>
              <Typography variant="body2" color="text.secondary">
                Valor de inventario
              </Typography>
              <Typography variant="h5" sx={{ fontWeight: 700 }}>
                {formatMoney(kpis.inventory.value)}
              </Typography>
            </Box>
            <Box>
              <Typography variant="body2" color="text.secondary">
                Productos activos
              </Typography>
              <Typography variant="h5" sx={{ fontWeight: 700 }}>
                {kpis.inventory.products_total.toLocaleString('es-ES')}
              </Typography>
            </Box>
            <Stack direction="row" spacing={1} useFlexGap sx={{ flexWrap: 'wrap' }}>
              {STATE_ORDER.map((state) => (
                <Chip
                  key={state}
                  onClick={() => onStateClick(state)}
                  label={`${state}: ${(kpis.inventory.counts[state] ?? 0).toLocaleString('es-ES')}`}
                  sx={{
                    bgcolor: STATE_COLORS[state],
                    color: '#FFFFFF',
                    fontWeight: 600,
                    cursor: 'pointer',
                    '&:hover': { bgcolor: STATE_COLORS[state], filter: 'brightness(0.93)' },
                  }}
                />
              ))}
            </Stack>
          </Stack>
        ) : null}
      </CardContent>
    </Card>
  )
}

// --- panel ---

export default function ResumenPanel({ onStateClick }: ResumenPanelProps) {
  const { token } = useAuth()

  const [dateFrom, setDateFrom] = useState(() => presetRange(30).from)
  const [dateTo, setDateTo] = useState(() => presetRange(30).to)
  const [category, setCategory] = useState('')
  const [groupBy, setGroupBy] = useState<TrendGroupBy>('day')

  const rangeValid = dateFrom !== '' && dateTo !== '' && dateFrom <= dateTo
  const scope = token && rangeValid ? `${token}:${dateFrom}:${dateTo}` : ''

  const categoriesState = useAsync(
    token ? `categories:${token}` : '',
    token ? () => fetchCategories(token) : null,
  )

  const kpisState = useAsync(
    scope ? `kpis:${scope}` : '',
    scope ? () => fetchKpis(token!, { date_from: dateFrom, date_to: dateTo }) : null,
  )

  const trendState = useAsync(
    scope ? `trend:${scope}:${category}:${groupBy}` : '',
    scope
      ? () =>
          fetchSalesTrend(token!, {
            group_by: groupBy,
            date_from: dateFrom,
            date_to: dateTo,
            category,
          })
      : null,
  )

  const byCategoryState = useAsync(
    scope ? `by-category:${scope}` : '',
    scope
      ? () => fetchSalesByCategory(token!, { date_from: dateFrom, date_to: dateTo })
      : null,
  )

  const topProductsState = useAsync(
    scope ? `top-products:${scope}:${category}` : '',
    scope
      ? () =>
          fetchTopProducts(token!, {
            date_from: dateFrom,
            date_to: dateTo,
            category,
            limit: 10,
          })
      : null,
  )

  const purchasesState = useAsync(
    scope ? `purchases:${scope}` : '',
    scope
      ? () => fetchPurchasesSummary(token!, { date_from: dateFrom, date_to: dateTo })
      : null,
  )

  const handleGroupBy = (_event: MouseEvent<HTMLElement>, value: TrendGroupBy | null) => {
    if (value !== null) setGroupBy(value)
  }

  const kpis = kpisState.data
  const categoryItems = (byCategoryState.data?.items ?? []).slice(0, CATEGORY_LIMIT)

  return (
    <Stack spacing={3}>
      <FilterBar
        dateFrom={dateFrom}
        dateTo={dateTo}
        onDateFromChange={setDateFrom}
        onDateToChange={setDateTo}
        categories={categoriesState.data?.categories ?? []}
        category={category}
        onCategoryChange={setCategory}
      />

      {!rangeValid && (
        <Alert severity="warning">
          El rango de fechas es inválido: «Desde» no puede ser posterior a «Hasta».
        </Alert>
      )}

      {kpisState.loading ? (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', lg: 'repeat(4, 1fr)' },
            gap: 2,
          }}
        >
          {[0, 1, 2, 3].map((index) => (
            <LoadingCard key={index} />
          ))}
        </Box>
      ) : kpisState.error ? (
        <Alert severity="error">{kpisState.error}</Alert>
      ) : kpis ? (
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', sm: 'repeat(2, 1fr)', lg: 'repeat(4, 1fr)' },
            gap: 2,
          }}
        >
          <KpiCard
            label="Total vendido"
            value={formatMoney(kpis.sales.total)}
            delta={kpis.sales.delta_pct.total}
          />
          <KpiCard
            label="Transacciones"
            value={kpis.sales.transactions.toLocaleString('es-ES')}
            delta={kpis.sales.delta_pct.transactions}
          />
          <KpiCard
            label="Ticket promedio"
            value={formatMoney(kpis.sales.avg_ticket)}
            delta={kpis.sales.delta_pct.avg_ticket}
          />
          <KpiCard
            label="Unidades vendidas"
            value={kpis.sales.units.toLocaleString('es-ES')}
            delta={kpis.sales.delta_pct.units}
          />
        </Box>
      ) : null}

      <InventoryCard
        kpis={kpis}
        loading={kpisState.loading}
        error={kpisState.error}
        onStateClick={onStateClick}
      />

      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', lg: 'repeat(2, 1fr)' },
          gap: 2,
        }}
      >
        <ChartCard
          title="Tendencia de ventas"
          subtitle="Total vendido por período"
          action={
            <ToggleButtonGroup
              size="small"
              exclusive
              value={groupBy}
              onChange={handleGroupBy}
            >
              <ToggleButton value="day">Día</ToggleButton>
              <ToggleButton value="week">Semana</ToggleButton>
              <ToggleButton value="month">Mes</ToggleButton>
            </ToggleButtonGroup>
          }
          loading={trendState.loading}
          error={trendState.error}
          empty={(trendState.data?.points.length ?? 0) === 0}
          height={320}
        >
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={trendState.data?.points ?? []}
              margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
            >
              <defs>
                <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={chartColors[0]} stopOpacity={0.35} />
                  <stop offset="95%" stopColor={chartColors[0]} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#EEF0F3" vertical={false} />
              <XAxis
                dataKey="bucket"
                tickFormatter={formatBucket}
                tick={{ fontSize: 12 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tickFormatter={formatAxisMoney}
                tick={{ fontSize: 12 }}
                tickLine={false}
                axisLine={false}
                width={70}
              />
              <Tooltip
                formatter={(value) => formatMoney(Number(value))}
                labelFormatter={(label) => formatBucket(String(label))}
              />
              <Area
                type="monotone"
                dataKey="total"
                name="Ventas"
                stroke={chartColors[0]}
                strokeWidth={2}
                fill="url(#trendFill)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Ventas por categoría"
          subtitle="Total vendido en el período (top 8)"
          loading={byCategoryState.loading}
          error={byCategoryState.error}
          empty={categoryItems.length === 0}
          height={320}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={categoryItems}
              margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#EEF0F3" vertical={false} />
              <XAxis
                dataKey="category"
                tick={{ fontSize: 11 }}
                angle={-25}
                textAnchor="end"
                height={80}
                interval={0}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tickFormatter={formatAxisMoney}
                tick={{ fontSize: 12 }}
                tickLine={false}
                axisLine={false}
                width={70}
              />
              <Tooltip
                formatter={(value) => formatMoney(Number(value))}
                cursor={{ fill: '#F3F4F6' }}
              />
              <Bar dataKey="total" name="Ventas" radius={[6, 6, 0, 0]}>
                {categoryItems.map((item, index) => (
                  <Cell
                    key={item.category}
                    fill={chartColors[index % chartColors.length]}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Top 10 productos"
          subtitle="Por total vendido en el período"
          loading={topProductsState.loading}
          error={topProductsState.error}
          empty={(topProductsState.data?.items.length ?? 0) === 0}
          height={340}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={topProductsState.data?.items ?? []}
              layout="vertical"
              margin={{ top: 0, right: 16, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#EEF0F3" horizontal={false} />
              <XAxis
                type="number"
                tickFormatter={formatAxisMoney}
                tick={{ fontSize: 12 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                type="category"
                dataKey="product_name"
                width={150}
                tick={{ fontSize: 11 }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                formatter={(value) => formatMoney(Number(value))}
                cursor={{ fill: '#F3F4F6' }}
              />
              <Bar
                dataKey="total"
                name="Ventas"
                fill={chartColors[0]}
                radius={[0, 6, 6, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Compras por mes"
          subtitle="Gasto de órdenes recibidas"
          loading={purchasesState.loading}
          error={purchasesState.error}
          empty={(purchasesState.data?.by_month.length ?? 0) === 0}
          height={320}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={purchasesState.data?.by_month ?? []}
              margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#EEF0F3" vertical={false} />
              <XAxis
                dataKey="month"
                tickFormatter={formatBucket}
                tick={{ fontSize: 12 }}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                tickFormatter={formatAxisMoney}
                tick={{ fontSize: 12 }}
                tickLine={false}
                axisLine={false}
                width={70}
              />
              <Tooltip
                formatter={(value) => formatMoney(Number(value))}
                labelFormatter={(label) => formatBucket(String(label))}
                cursor={{ fill: '#F3F4F6' }}
              />
              <Bar
                dataKey="spend"
                name="Gasto"
                fill={chartColors[2]}
                radius={[6, 6, 0, 0]}
              />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </Box>
    </Stack>
  )
}
