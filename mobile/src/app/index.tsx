import { useState } from 'react';
import { ActivityIndicator, Pressable, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { ThemedView } from '@/components/themed-view';
import { getApiConfig } from '@/config/api';
import { BottomTabInset, MaxContentWidth, Spacing } from '@/constants/theme';
import { useTheme } from '@/hooks/use-theme';
import { checkHealth } from '@/services/health';

type Status =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'connected'; checkedAt: Date }
  | { kind: 'error'; message: string };

const apiConfig = getApiConfig();

export default function ConnectionScreen() {
  const theme = useTheme();
  const [status, setStatus] = useState<Status>({ kind: 'idle' });

  async function runCheck() {
    if (!apiConfig.ok) {
      setStatus({ kind: 'error', message: apiConfig.reason });
      return;
    }
    setStatus({ kind: 'loading' });
    const result = await checkHealth(apiConfig.baseUrl);
    setStatus(
      result.ok ? { kind: 'connected', checkedAt: new Date() } : { kind: 'error', message: result.message }
    );
  }

  const isLoading = status.kind === 'loading';
  const buttonLabel = status.kind === 'error' ? 'Reintentar' : 'Comprobar conexión';

  return (
    <ThemedView style={styles.container}>
      <SafeAreaView style={styles.safeArea}>
        <ThemedText type="subtitle">Conexión con backend</ThemedText>

        <ThemedView type="backgroundElement" style={styles.card}>
          <ThemedText type="smallBold">URL</ThemedText>
          <ThemedText type="code" selectable>
            {apiConfig.ok ? `${apiConfig.baseUrl}/health` : 'sin configurar'}
          </ThemedText>

          <ThemedText type="smallBold">Estado</ThemedText>
          {status.kind === 'idle' && <ThemedText>Sin comprobar</ThemedText>}
          {status.kind === 'loading' && (
            <ThemedView type="backgroundElement" style={styles.row}>
              <ActivityIndicator color={theme.text} />
              <ThemedText>Comprobando…</ThemedText>
            </ThemedView>
          )}
          {status.kind === 'connected' && (
            <ThemedText style={styles.ok}>
              Conectado ({status.checkedAt.toLocaleTimeString()})
            </ThemedText>
          )}
          {status.kind === 'error' && (
            <ThemedText style={styles.error}>Error: {status.message}</ThemedText>
          )}
        </ThemedView>

        <Pressable
          accessibilityRole="button"
          disabled={isLoading}
          onPress={runCheck}
          style={({ pressed }) => [
            styles.button,
            { backgroundColor: theme.text, opacity: isLoading ? 0.5 : pressed ? 0.8 : 1 },
          ]}>
          <ThemedText style={{ color: theme.background }}>{buttonLabel}</ThemedText>
        </Pressable>
      </SafeAreaView>
    </ThemedView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    flexDirection: 'row',
    justifyContent: 'center',
  },
  safeArea: {
    flex: 1,
    maxWidth: MaxContentWidth,
    justifyContent: 'center',
    gap: Spacing.four,
    paddingHorizontal: Spacing.four,
    paddingBottom: BottomTabInset + Spacing.three,
  },
  card: {
    gap: Spacing.two,
    padding: Spacing.four,
    borderRadius: Spacing.four,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: Spacing.two,
  },
  ok: {
    color: '#2e9e5b',
  },
  error: {
    color: '#d6453d',
  },
  button: {
    alignItems: 'center',
    paddingVertical: Spacing.three,
    borderRadius: Spacing.three,
  },
});
