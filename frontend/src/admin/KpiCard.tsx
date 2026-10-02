import { Card, CardContent, Chip, Stack, Typography } from '@mui/material'
import { formatPct } from '../api/shared'

export interface KpiCardProps {
  label: string
  value: string
  delta: number | null
}

type DeltaColor = 'default' | 'success' | 'error'

export default function KpiCard({ label, value, delta }: KpiCardProps) {
  const color: DeltaColor =
    delta === null ? 'default' : delta > 0 ? 'success' : delta < 0 ? 'error' : 'default'

  return (
    <Card
      variant="outlined"
      sx={{
        height: '100%',
        borderRadius: '14px',
        borderColor: '#E5E7EB',
        boxShadow: 'none',
      }}
    >
      <CardContent>
        <Stack spacing={1.5}>
          <Typography variant="body2" color="text.secondary" sx={{ fontWeight: 500 }}>
            {label}
          </Typography>
          <Typography variant="h4" sx={{ fontWeight: 700 }}>
            {value}
          </Typography>
          <Chip
            size="small"
            color={color}
            label={formatPct(delta)}
            sx={{ alignSelf: 'flex-start' }}
          />
        </Stack>
      </CardContent>
    </Card>
  )
}
