/** Perfil: gustos declarados, gestión local de datos y diagnóstico de conexión (sin cuenta). */
import { router } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { Body, Button, Chip, Display, Meta, Notice, Screen, Section } from '@/components/ui';
import { C, Space } from '@/constants/theme';
import { EDITORIAL_STYLES } from '@/constants/styles';
import { getApiConfig } from '@/config/api';
import { checkHealth } from '@/services/health';
import { useLibrary } from '@/state/library';

type Health = { kind: 'idle' } | { kind: 'loading' } | { kind: 'ok' } | { kind: 'error'; message: string };

export default function Profile() {
  const lib = useLibrary();
  const api = getApiConfig();
  const [health, setHealth] = useState<Health>({ kind: 'idle' });
  const styles_ = lib.preferences.declared_styles;

  async function runCheck() {
    if (!api.ok) return setHealth({ kind: 'error', message: api.reason });
    setHealth({ kind: 'loading' });
    const result = await checkHealth(api.baseUrl);
    setHealth(result.ok ? { kind: 'ok' } : { kind: 'error', message: result.message });
  }

  const toggle = (s: string) => lib.setDeclaredStyles(styles_.includes(s) ? styles_.filter((x) => x !== s) : [...styles_, s]);

  return (
    <Screen>
      <Display>Perfil</Display>
      <Body muted>Sin cuenta: todo lo que eliges se guarda solo en este dispositivo.</Body>

      <Section label={`Canciones guardadas · ${lib.savedTracks.length}`}>
        <Button label="Ver Guardados" variant="ghost" onPress={() => router.navigate('/saved')} />
      </Section>

      <Section label={`Artistas de partida de Inicio · ${lib.favorites.length}`}>
        <Button label="Editar artistas" variant="ghost" onPress={() => router.push('/onboarding?mode=edit')} />
      </Section>

      <Section label="Estilos que te gustan (opcional)">
        <View style={styles.wrap}>
          {EDITORIAL_STYLES.map((s) => (
            <Chip key={s} label={s} selected={styles_.includes(s)} onPress={() => toggle(s)} />
          ))}
        </View>
        <Notice>Lista editorial propia. Por ahora se guarda tu elección, pero todavía no cambia las recomendaciones.</Notice>
      </Section>

      <Section label={`Descartados · ${lib.discarded.length}`}>
        <Button label="Volver a mostrar descartados" variant="ghost" disabled={!lib.discarded.length} onPress={lib.resetDiscarded} />
      </Section>

      <Section label="Conexión con el servidor">
        <Meta selectable>{api.ok ? api.baseUrl : api.reason}</Meta>
        <Button label={health.kind === 'loading' ? 'Comprobando…' : 'Comprobar conexión'} variant="ghost" disabled={health.kind === 'loading'} onPress={runCheck} />
        {health.kind === 'ok' ? <Body style={{ color: C.acid }}>Conectado</Body> : null}
        {health.kind === 'error' ? <Body style={{ color: C.danger }}>{health.message}</Body> : null}
      </Section>

      <Section label="Datos">
        <Body muted>
          Canciones, artistas y conexiones: MusicBrainz (datos centrales, CC0), Wikidata y Discogs (CC0), consultados a
          través del servidor de Chromatic Underground. Sin audio: BPM, tonalidad y energía solo aparecerán con una medición real.
        </Body>
      </Section>
    </Screen>
  );
}

const styles = StyleSheet.create({
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: Space.sm },
});
