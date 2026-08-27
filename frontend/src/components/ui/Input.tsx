import React from "react";
import {
  KeyboardTypeOptions,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { useTheme } from "@/src/theme/ThemeProvider";
import { fonts, fontSize, radius, spacing } from "@/src/theme/tokens";

type Props = {
  label?: string;
  value: string;
  onChangeText: (t: string) => void;
  placeholder?: string;
  keyboardType?: KeyboardTypeOptions;
  autoFocus?: boolean;
  maxLength?: number;
  error?: string | null;
  editable?: boolean;
  autoCapitalize?: "none" | "sentences" | "words" | "characters";
  autoCorrect?: boolean;
  secureTextEntry?: boolean;
  center?: boolean;
  testID?: string;
};

export function Input({
  label,
  value,
  onChangeText,
  placeholder,
  keyboardType,
  autoFocus,
  maxLength,
  error,
  editable = true,
  autoCapitalize = "none",
  autoCorrect = false,
  secureTextEntry = false,
  center = false,
  testID,
}: Props) {
  const { colors } = useTheme();
  return (
    <View style={{ gap: spacing.xs }}>
      {label ? (
        <Text style={[styles.label, { color: colors.onSurfaceSecondary }]}>{label}</Text>
      ) : null}
      <TextInput
        testID={testID}
        value={value}
        onChangeText={onChangeText}
        placeholder={placeholder}
        placeholderTextColor={colors.onSurfaceTertiary}
        keyboardType={keyboardType}
        autoFocus={autoFocus}
        maxLength={maxLength}
        editable={editable}
        autoCapitalize={autoCapitalize}
        autoCorrect={autoCorrect}
        secureTextEntry={secureTextEntry}
        style={[
          styles.input,
          {
            backgroundColor: colors.surfaceSecondary,
            borderColor: error ? colors.error : colors.border,
            color: colors.onSurface,
            textAlign: center ? "center" : "left",
            letterSpacing: center ? 8 : 0,
          },
        ]}
      />
      {error ? <Text style={[styles.error, { color: colors.error }]}>{error}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  label: { fontFamily: fonts.medium, fontSize: fontSize.sm },
  input: {
    height: 52,
    borderRadius: radius.md,
    borderWidth: 1,
    paddingHorizontal: spacing.lg,
    fontFamily: fonts.medium,
    fontSize: fontSize.lg,
  },
  error: { fontFamily: fonts.medium, fontSize: fontSize.sm },
});