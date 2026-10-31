export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.18"
  }
  public: {
    Tables: {
      boundaries: {
        Row: {
          as_of: string | null
          boundary_id: string
          geom: unknown
          kind: string
          name: string
          source: string | null
        }
        Insert: {
          as_of?: string | null
          boundary_id: string
          geom: unknown
          kind: string
          name: string
          source?: string | null
        }
        Update: {
          as_of?: string | null
          boundary_id?: string
          geom?: unknown
          kind?: string
          name?: string
          source?: string | null
        }
        Relationships: []
      }
      check_results: {
        Row: {
          call: string
          change_pct_hi: number | null
          change_pct_lo: number | null
          change_pct_med: number | null
          check_id: string
          check_run_id: string
          colour: string
          controls: string | null
          de_t_yr_hi: number | null
          de_t_yr_lo: number | null
          de_t_yr_med: number | null
          diag_ok: boolean | null
          effect_hi: number | null
          effect_lo: number | null
          effect_med: number | null
          evidence: string
          mde_pct: number | null
          n_after: number
          n_before: number
          p_decrease: number | null
          plain_reading: string
          provisional: boolean
          publish_id: string
          reason: string | null
          restricted: boolean
          site_id: string
          size: string | null
        }
        Insert: {
          call: string
          change_pct_hi?: number | null
          change_pct_lo?: number | null
          change_pct_med?: number | null
          check_id: string
          check_run_id: string
          colour: string
          controls?: string | null
          de_t_yr_hi?: number | null
          de_t_yr_lo?: number | null
          de_t_yr_med?: number | null
          diag_ok?: boolean | null
          effect_hi?: number | null
          effect_lo?: number | null
          effect_med?: number | null
          evidence: string
          mde_pct?: number | null
          n_after: number
          n_before: number
          p_decrease?: number | null
          plain_reading: string
          provisional?: boolean
          publish_id: string
          reason?: string | null
          restricted?: boolean
          site_id: string
          size?: string | null
        }
        Update: {
          call?: string
          change_pct_hi?: number | null
          change_pct_lo?: number | null
          change_pct_med?: number | null
          check_id?: string
          check_run_id?: string
          colour?: string
          controls?: string | null
          de_t_yr_hi?: number | null
          de_t_yr_lo?: number | null
          de_t_yr_med?: number | null
          diag_ok?: boolean | null
          effect_hi?: number | null
          effect_lo?: number | null
          effect_med?: number | null
          evidence?: string
          mde_pct?: number | null
          n_after?: number
          n_before?: number
          p_decrease?: number | null
          plain_reading?: string
          provisional?: boolean
          publish_id?: string
          reason?: string | null
          restricted?: boolean
          site_id?: string
          size?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "check_results_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "publications"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "check_results_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_publication"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "check_results_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_review_publication"
            referencedColumns: ["publish_id"]
          },
        ]
      }
      checks: {
        Row: {
          check_id: string
          check_type: string
          date_confidence: string
          date_end: string | null
          date_start: string
          description: string
          entered_on: string | null
          publish_id: string
          repair_kind: string | null
          site_id: string
          source_doc: string
          source_doc_title: string | null
          source_page: string | null
          source_url: string | null
        }
        Insert: {
          check_id: string
          check_type: string
          date_confidence: string
          date_end?: string | null
          date_start: string
          description: string
          entered_on?: string | null
          publish_id: string
          repair_kind?: string | null
          site_id: string
          source_doc: string
          source_doc_title?: string | null
          source_page?: string | null
          source_url?: string | null
        }
        Update: {
          check_id?: string
          check_type?: string
          date_confidence?: string
          date_end?: string | null
          date_start?: string
          description?: string
          entered_on?: string | null
          publish_id?: string
          repair_kind?: string | null
          site_id?: string
          source_doc?: string
          source_doc_title?: string | null
          source_page?: string | null
          source_url?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "checks_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "publications"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "checks_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_publication"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "checks_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_review_publication"
            referencedColumns: ["publish_id"]
          },
        ]
      }
      data_terms: {
        Row: {
          checked_on: string | null
          confirmed: boolean
          credit_line: string | null
          derived_publishable: boolean
          display_name: string
          raw_publishable: boolean
          source: string
          terms_url: string | null
        }
        Insert: {
          checked_on?: string | null
          confirmed?: boolean
          credit_line?: string | null
          derived_publishable?: boolean
          display_name: string
          raw_publishable?: boolean
          source: string
          terms_url?: string | null
        }
        Update: {
          checked_on?: string | null
          confirmed?: boolean
          credit_line?: string | null
          derived_publishable?: boolean
          display_name?: string
          raw_publishable?: boolean
          source?: string
          terms_url?: string | null
        }
        Relationships: []
      }
      neighbours: {
        Row: {
          distance_m: number | null
          geom: unknown
          kind: string
          name: string
          nearest_site_id: string | null
          neighbour_id: string
          publish_id: string
          source: string | null
        }
        Insert: {
          distance_m?: number | null
          geom: unknown
          kind: string
          name: string
          nearest_site_id?: string | null
          neighbour_id: string
          publish_id: string
          source?: string | null
        }
        Update: {
          distance_m?: number | null
          geom?: unknown
          kind?: string
          name?: string
          nearest_site_id?: string | null
          neighbour_id?: string
          publish_id?: string
          source?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "neighbours_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "publications"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "neighbours_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_publication"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "neighbours_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_review_publication"
            referencedColumns: ["publish_id"]
          },
        ]
      }
      operator_reports: {
        Row: {
          facility_id: string
          gwp_confirmed: boolean
          gwp_used: number | null
          publish_id: string
          reported_ch4_t: number
          reported_co2e_t: number | null
          site_id: string
          source: string
          url: string
          year: number
        }
        Insert: {
          facility_id: string
          gwp_confirmed?: boolean
          gwp_used?: number | null
          publish_id: string
          reported_ch4_t: number
          reported_co2e_t?: number | null
          site_id: string
          source: string
          url: string
          year: number
        }
        Update: {
          facility_id?: string
          gwp_confirmed?: boolean
          gwp_used?: number | null
          publish_id?: string
          reported_ch4_t?: number
          reported_co2e_t?: number | null
          site_id?: string
          source?: string
          url?: string
          year?: number
        }
        Relationships: [
          {
            foreignKeyName: "operator_reports_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "publications"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "operator_reports_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_publication"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "operator_reports_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_review_publication"
            referencedColumns: ["publish_id"]
          },
        ]
      }
      passes: {
        Row: {
          acquired_utc: string
          coverage_frac: number | null
          coverage_source: string | null
          detected: boolean
          instrument: string
          n_plumes: number
          overpass_id: string
          publish_id: string
          q_obs_kg_hr: number | null
          restricted: boolean
          site_id: string
          usable: boolean
          valid_frac: number | null
        }
        Insert: {
          acquired_utc: string
          coverage_frac?: number | null
          coverage_source?: string | null
          detected?: boolean
          instrument: string
          n_plumes?: number
          overpass_id: string
          publish_id: string
          q_obs_kg_hr?: number | null
          restricted?: boolean
          site_id: string
          usable: boolean
          valid_frac?: number | null
        }
        Update: {
          acquired_utc?: string
          coverage_frac?: number | null
          coverage_source?: string | null
          detected?: boolean
          instrument?: string
          n_plumes?: number
          overpass_id?: string
          publish_id?: string
          q_obs_kg_hr?: number | null
          restricted?: boolean
          site_id?: string
          usable?: boolean
          valid_frac?: number | null
        }
        Relationships: [
          {
            foreignKeyName: "passes_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "publications"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "passes_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_publication"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "passes_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_review_publication"
            referencedColumns: ["publish_id"]
          },
        ]
      }
      plumes: {
        Row: {
          acquired_utc: string
          attribution: string
          data_version: string | null
          distance_m: number | null
          geom: unknown
          instrument: string
          lat: number
          lon: number
          new_in_update: boolean
          overpass_id: string | null
          plume_id: string
          publish_id: string
          q_kg_hr: number | null
          q_sigma_kg_hr: number | null
          restricted: boolean
          site_id: string | null
          source: string
        }
        Insert: {
          acquired_utc: string
          attribution: string
          data_version?: string | null
          distance_m?: number | null
          geom?: unknown
          instrument: string
          lat: number
          lon: number
          new_in_update?: boolean
          overpass_id?: string | null
          plume_id: string
          publish_id: string
          q_kg_hr?: number | null
          q_sigma_kg_hr?: number | null
          restricted?: boolean
          site_id?: string | null
          source: string
        }
        Update: {
          acquired_utc?: string
          attribution?: string
          data_version?: string | null
          distance_m?: number | null
          geom?: unknown
          instrument?: string
          lat?: number
          lon?: number
          new_in_update?: boolean
          overpass_id?: string | null
          plume_id?: string
          publish_id?: string
          q_kg_hr?: number | null
          q_sigma_kg_hr?: number | null
          restricted?: boolean
          site_id?: string | null
          source?: string
        }
        Relationships: [
          {
            foreignKeyName: "plumes_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "publications"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "plumes_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_publication"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "plumes_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_review_publication"
            referencedColumns: ["publish_id"]
          },
        ]
      }
      population_context: {
        Row: {
          label: string
          publish_id: string
          radius_km: number
          residents: number
          site_id: string
        }
        Insert: {
          label: string
          publish_id: string
          radius_km: number
          residents: number
          site_id: string
        }
        Update: {
          label?: string
          publish_id?: string
          radius_km?: number
          residents?: number
          site_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "population_context_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "publications"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "population_context_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_publication"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "population_context_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_review_publication"
            referencedColumns: ["publish_id"]
          },
        ]
      }
      publications: {
        Row: {
          check_run_id: string | null
          created_at: string
          data_through: string | null
          git_dirty: boolean | null
          git_sha: string | null
          model_run_id: string | null
          notes: string | null
          provisional: boolean
          publish_id: string
          published_at: string | null
          refresh_id: string | null
          simulated: boolean
          source_lag_days: number
          visibility: string
        }
        Insert: {
          check_run_id?: string | null
          created_at?: string
          data_through?: string | null
          git_dirty?: boolean | null
          git_sha?: string | null
          model_run_id?: string | null
          notes?: string | null
          provisional?: boolean
          publish_id: string
          published_at?: string | null
          refresh_id?: string | null
          simulated?: boolean
          source_lag_days?: number
          visibility?: string
        }
        Update: {
          check_run_id?: string | null
          created_at?: string
          data_through?: string | null
          git_dirty?: boolean | null
          git_sha?: string | null
          model_run_id?: string | null
          notes?: string | null
          provisional?: boolean
          publish_id?: string
          published_at?: string | null
          refresh_id?: string | null
          simulated?: boolean
          source_lag_days?: number
          visibility?: string
        }
        Relationships: []
      }
      runs: {
        Row: {
          config_sha256: Json | null
          created_at: string | null
          git_dirty: boolean | null
          git_sha: string | null
          kind: string
          manifest: Json
          run_id: string
          versions: Json | null
        }
        Insert: {
          config_sha256?: Json | null
          created_at?: string | null
          git_dirty?: boolean | null
          git_sha?: string | null
          kind: string
          manifest?: Json
          run_id: string
          versions?: Json | null
        }
        Update: {
          config_sha256?: Json | null
          created_at?: string | null
          git_dirty?: boolean | null
          git_sha?: string | null
          kind?: string
          manifest?: Json
          run_id?: string
          versions?: Json | null
        }
        Relationships: []
      }
      site_estimates: {
        Row: {
          divergences: number | null
          e_t_yr_hi: number | null
          e_t_yr_lo: number | null
          e_t_yr_med: number | null
          ess_bulk_min: number | null
          f_hi: number | null
          f_lo: number | null
          f_med: number | null
          insufficient_reason: string | null
          model_run_id: string
          n_detections: number
          n_usable_overpasses: number
          period: string
          provisional: boolean
          publish_id: string
          qbar_kg_hr_hi: number | null
          qbar_kg_hr_lo: number | null
          qbar_kg_hr_med: number | null
          restricted: boolean
          rhat_max: number | null
          site_id: string
          status: string
        }
        Insert: {
          divergences?: number | null
          e_t_yr_hi?: number | null
          e_t_yr_lo?: number | null
          e_t_yr_med?: number | null
          ess_bulk_min?: number | null
          f_hi?: number | null
          f_lo?: number | null
          f_med?: number | null
          insufficient_reason?: string | null
          model_run_id: string
          n_detections: number
          n_usable_overpasses: number
          period?: string
          provisional?: boolean
          publish_id: string
          qbar_kg_hr_hi?: number | null
          qbar_kg_hr_lo?: number | null
          qbar_kg_hr_med?: number | null
          restricted?: boolean
          rhat_max?: number | null
          site_id: string
          status: string
        }
        Update: {
          divergences?: number | null
          e_t_yr_hi?: number | null
          e_t_yr_lo?: number | null
          e_t_yr_med?: number | null
          ess_bulk_min?: number | null
          f_hi?: number | null
          f_lo?: number | null
          f_med?: number | null
          insufficient_reason?: string | null
          model_run_id?: string
          n_detections?: number
          n_usable_overpasses?: number
          period?: string
          provisional?: boolean
          publish_id?: string
          qbar_kg_hr_hi?: number | null
          qbar_kg_hr_lo?: number | null
          qbar_kg_hr_med?: number | null
          restricted?: boolean
          rhat_max?: number | null
          site_id?: string
          status?: string
        }
        Relationships: [
          {
            foreignKeyName: "site_estimates_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "publications"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "site_estimates_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_publication"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "site_estimates_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_review_publication"
            referencedColumns: ["publish_id"]
          },
        ]
      }
      site_features: {
        Row: {
          area_km2: number | null
          closed: boolean
          dist_neighbor_m: number | null
          ghgrp_reporter: boolean
          publish_id: string
          site_id: string
        }
        Insert: {
          area_km2?: number | null
          closed: boolean
          dist_neighbor_m?: number | null
          ghgrp_reporter: boolean
          publish_id: string
          site_id: string
        }
        Update: {
          area_km2?: number | null
          closed?: boolean
          dist_neighbor_m?: number | null
          ghgrp_reporter?: boolean
          publish_id?: string
          site_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "site_features_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "publications"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "site_features_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_publication"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "site_features_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_review_publication"
            referencedColumns: ["publish_id"]
          },
        ]
      }
      sites: {
        Row: {
          area_km2: number | null
          centroid: unknown
          city: string | null
          county: string | null
          ghgrp_facility_id: string | null
          name: string
          operator: string | null
          outline: unknown
          polygon_source: string | null
          provisional: boolean
          publish_id: string
          site_id: string
          status: string | null
          swis_number: string | null
          tier: string | null
        }
        Insert: {
          area_km2?: number | null
          centroid?: unknown
          city?: string | null
          county?: string | null
          ghgrp_facility_id?: string | null
          name: string
          operator?: string | null
          outline?: unknown
          polygon_source?: string | null
          provisional?: boolean
          publish_id: string
          site_id: string
          status?: string | null
          swis_number?: string | null
          tier?: string | null
        }
        Update: {
          area_km2?: number | null
          centroid?: unknown
          city?: string | null
          county?: string | null
          ghgrp_facility_id?: string | null
          name?: string
          operator?: string | null
          outline?: unknown
          polygon_source?: string | null
          provisional?: boolean
          publish_id?: string
          site_id?: string
          status?: string | null
          swis_number?: string | null
          tier?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "sites_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "publications"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "sites_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_publication"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "sites_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_review_publication"
            referencedColumns: ["publish_id"]
          },
        ]
      }
      update_log: {
        Row: {
          count: number | null
          data_through: string | null
          event_date: string | null
          item_order: number
          kind: string
          publish_id: string
          site_id: string | null
          text: string
        }
        Insert: {
          count?: number | null
          data_through?: string | null
          event_date?: string | null
          item_order: number
          kind: string
          publish_id: string
          site_id?: string | null
          text: string
        }
        Update: {
          count?: number | null
          data_through?: string | null
          event_date?: string | null
          item_order?: number
          kind?: string
          publish_id?: string
          site_id?: string | null
          text?: string
        }
        Relationships: [
          {
            foreignKeyName: "update_log_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "publications"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "update_log_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_publication"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "update_log_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_review_publication"
            referencedColumns: ["publish_id"]
          },
        ]
      }
      validation_results: {
        Row: {
          created_at: string | null
          gate: string
          metrics: Json
          note: string | null
          publish_id: string
          report_id: string
          result: string
          run_id: string | null
          superseded: boolean
        }
        Insert: {
          created_at?: string | null
          gate: string
          metrics?: Json
          note?: string | null
          publish_id: string
          report_id: string
          result: string
          run_id?: string | null
          superseded?: boolean
        }
        Update: {
          created_at?: string | null
          gate?: string
          metrics?: Json
          note?: string | null
          publish_id?: string
          report_id?: string
          result?: string
          run_id?: string | null
          superseded?: boolean
        }
        Relationships: [
          {
            foreignKeyName: "validation_results_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "publications"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "validation_results_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_publication"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "validation_results_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_review_publication"
            referencedColumns: ["publish_id"]
          },
        ]
      }
    }
    Views: {
      v_boundaries: {
        Row: {
          as_of: string | null
          boundary_id: string | null
          geojson: Json | null
          kind: string | null
          name: string | null
          source: string | null
        }
        Insert: {
          as_of?: string | null
          boundary_id?: string | null
          geojson?: never
          kind?: string | null
          name?: string | null
          source?: string | null
        }
        Update: {
          as_of?: string | null
          boundary_id?: string | null
          geojson?: never
          kind?: string | null
          name?: string | null
          source?: string | null
        }
        Relationships: []
      }
      v_checks_with_results: {
        Row: {
          call: string | null
          change_pct_hi: number | null
          change_pct_lo: number | null
          change_pct_med: number | null
          check_id: string | null
          check_run_id: string | null
          check_type: string | null
          colour: string | null
          controls: string | null
          date_confidence: string | null
          date_end: string | null
          date_start: string | null
          de_t_yr_hi: number | null
          de_t_yr_lo: number | null
          de_t_yr_med: number | null
          description: string | null
          diag_ok: boolean | null
          effect_hi: number | null
          effect_lo: number | null
          effect_med: number | null
          evidence: string | null
          mde_pct: number | null
          n_after: number | null
          n_before: number | null
          p_decrease: number | null
          plain_reading: string | null
          provisional: boolean | null
          publish_id: string | null
          reason: string | null
          repair_kind: string | null
          restricted: boolean | null
          site_id: string | null
          size: string | null
          source_doc: string | null
          source_doc_title: string | null
          source_page: string | null
          source_url: string | null
        }
        Relationships: [
          {
            foreignKeyName: "checks_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "publications"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "checks_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_publication"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "checks_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_review_publication"
            referencedColumns: ["publish_id"]
          },
        ]
      }
      v_current_publication: {
        Row: {
          check_run_id: string | null
          created_at: string | null
          data_through: string | null
          git_dirty: boolean | null
          git_sha: string | null
          model_run_id: string | null
          notes: string | null
          provisional: boolean | null
          publish_id: string | null
          published_at: string | null
          refresh_id: string | null
          simulated: boolean | null
          source_lag_days: number | null
          visibility: string | null
        }
        Relationships: []
      }
      v_current_review_publication: {
        Row: {
          check_run_id: string | null
          created_at: string | null
          data_through: string | null
          git_dirty: boolean | null
          git_sha: string | null
          model_run_id: string | null
          notes: string | null
          provisional: boolean | null
          publish_id: string | null
          published_at: string | null
          refresh_id: string | null
          simulated: boolean | null
          source_lag_days: number | null
          visibility: string | null
        }
        Relationships: []
      }
      v_neighbours: {
        Row: {
          distance_m: number | null
          geojson: Json | null
          kind: string | null
          name: string | null
          nearest_site_id: string | null
          neighbour_id: string | null
          publish_id: string | null
          source: string | null
        }
        Insert: {
          distance_m?: number | null
          geojson?: never
          kind?: string | null
          name?: string | null
          nearest_site_id?: string | null
          neighbour_id?: string | null
          publish_id?: string | null
          source?: string | null
        }
        Update: {
          distance_m?: number | null
          geojson?: never
          kind?: string | null
          name?: string | null
          nearest_site_id?: string | null
          neighbour_id?: string | null
          publish_id?: string | null
          source?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "neighbours_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "publications"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "neighbours_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_publication"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "neighbours_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_review_publication"
            referencedColumns: ["publish_id"]
          },
        ]
      }
      v_operator_comparison: {
        Row: {
          e_t_yr_hi: number | null
          e_t_yr_lo: number | null
          e_t_yr_med: number | null
          gwp_confirmed: boolean | null
          gwp_used: number | null
          model_run_id: string | null
          period: string | null
          provisional: boolean | null
          publish_id: string | null
          reported_ch4_t: number | null
          reported_co2e_t: number | null
          reported_source: string | null
          reported_url: string | null
          reported_year: number | null
          restricted: boolean | null
          site_id: string | null
          status: string | null
        }
        Relationships: [
          {
            foreignKeyName: "site_estimates_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "publications"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "site_estimates_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_publication"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "site_estimates_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_review_publication"
            referencedColumns: ["publish_id"]
          },
        ]
      }
      v_pass_months: {
        Row: {
          instrument: string | null
          month: string | null
          n_detected: number | null
          n_passes: number | null
          n_usable: number | null
          publish_id: string | null
          restricted: boolean | null
          site_id: string | null
        }
        Relationships: [
          {
            foreignKeyName: "passes_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "publications"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "passes_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_publication"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "passes_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_review_publication"
            referencedColumns: ["publish_id"]
          },
        ]
      }
      v_plume_days: {
        Row: {
          includes_restricted: boolean | null
          plume_days: number | null
          plume_days_per_usable_pass: number | null
          publish_id: string | null
          site_id: string | null
          usable_passes: number | null
        }
        Relationships: [
          {
            foreignKeyName: "passes_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "publications"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "passes_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_publication"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "passes_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_review_publication"
            referencedColumns: ["publish_id"]
          },
        ]
      }
      v_plumes: {
        Row: {
          acquired_utc: string | null
          attribution: string | null
          data_version: string | null
          distance_m: number | null
          instrument: string | null
          lat: number | null
          lon: number | null
          new_in_update: boolean | null
          overpass_id: string | null
          plume_id: string | null
          publish_id: string | null
          q_kg_hr: number | null
          q_sigma_kg_hr: number | null
          restricted: boolean | null
          site_id: string | null
          source: string | null
        }
        Insert: {
          acquired_utc?: string | null
          attribution?: string | null
          data_version?: string | null
          distance_m?: number | null
          instrument?: string | null
          lat?: number | null
          lon?: number | null
          new_in_update?: boolean | null
          overpass_id?: string | null
          plume_id?: string | null
          publish_id?: string | null
          q_kg_hr?: number | null
          q_sigma_kg_hr?: number | null
          restricted?: boolean | null
          site_id?: string | null
          source?: string | null
        }
        Update: {
          acquired_utc?: string | null
          attribution?: string | null
          data_version?: string | null
          distance_m?: number | null
          instrument?: string | null
          lat?: number | null
          lon?: number | null
          new_in_update?: boolean | null
          overpass_id?: string | null
          plume_id?: string | null
          publish_id?: string | null
          q_kg_hr?: number | null
          q_sigma_kg_hr?: number | null
          restricted?: boolean | null
          site_id?: string | null
          source?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "plumes_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "publications"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "plumes_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_publication"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "plumes_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_review_publication"
            referencedColumns: ["publish_id"]
          },
        ]
      }
      v_sites: {
        Row: {
          area_km2: number | null
          city: string | null
          county: string | null
          ghgrp_facility_id: string | null
          lat: number | null
          lon: number | null
          name: string | null
          operator: string | null
          outline_geojson: Json | null
          polygon_source: string | null
          provisional: boolean | null
          publish_id: string | null
          site_id: string | null
          status: string | null
          swis_number: string | null
          tier: string | null
        }
        Insert: {
          area_km2?: number | null
          city?: string | null
          county?: string | null
          ghgrp_facility_id?: string | null
          lat?: never
          lon?: never
          name?: string | null
          operator?: string | null
          outline_geojson?: never
          polygon_source?: string | null
          provisional?: boolean | null
          publish_id?: string | null
          site_id?: string | null
          status?: string | null
          swis_number?: string | null
          tier?: string | null
        }
        Update: {
          area_km2?: number | null
          city?: string | null
          county?: string | null
          ghgrp_facility_id?: string | null
          lat?: never
          lon?: never
          name?: string | null
          operator?: string | null
          outline_geojson?: never
          polygon_source?: string | null
          provisional?: boolean | null
          publish_id?: string | null
          site_id?: string | null
          status?: string | null
          swis_number?: string | null
          tier?: string | null
        }
        Relationships: [
          {
            foreignKeyName: "sites_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "publications"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "sites_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_publication"
            referencedColumns: ["publish_id"]
          },
          {
            foreignKeyName: "sites_publish_id_fkey"
            columns: ["publish_id"]
            isOneToOne: false
            referencedRelation: "v_current_review_publication"
            referencedColumns: ["publish_id"]
          },
        ]
      }
    }
    Functions: {
      [_ in never]: never
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends (DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never) = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends (PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never) = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {},
  },
} as const
