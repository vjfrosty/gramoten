<?php
/**
 * Plugin Name:       Грамотен
 * Plugin URI:        https://github.com/vjfrosty/gramoten
 * Description:       Проверка на правопис, граматика, пунктуация и формат на български в редактора на блокове. Работи изцяло в браузъра, текстът не излиза от него.
 * Version:           0.1.0
 * Requires at least: 6.6
 * Requires PHP:      7.4
 * Author:            Yasen Ivanov
 * Author URI:        https://github.com/vjfrosty
 * License:           GPL-3.0-or-later
 * License URI:       https://www.gnu.org/licenses/gpl-3.0.html
 * Text Domain:       gramoten
 *
 * @package Gramoten
 */

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

define( 'GRAMOTEN_VERSION', '0.1.0' );

/**
 * The personal dictionary: each user's own, reachable through the REST API by that user only.
 */
function gramoten_register_meta() {
	register_meta(
		'user',
		'gramoten_words',
		array(
			'type'              => 'array',
			'single'            => true,
			'default'           => array(),
			'sanitize_callback' => 'gramoten_sanitize_words',
			'auth_callback'     => function ( $allowed, $meta_key, $user_id ) {
				return get_current_user_id() === (int) $user_id;
			},
			'show_in_rest'      => array(
				'schema' => array(
					'type'  => 'array',
					'items' => array( 'type' => 'string' ),
				),
			),
		)
	);
}
add_action( 'init', 'gramoten_register_meta' );

/**
 * The words as one lowercase word each, without duplicates.
 *
 * @param mixed $words What the request sent.
 * @return string[]
 */
function gramoten_sanitize_words( $words ) {
	$clean = array();
	foreach ( (array) $words as $word ) {
		$word = mb_strtolower( trim( sanitize_text_field( (string) $word ) ), 'UTF-8' );
		if ( '' !== $word ) {
			$clean[ $word ] = true;
		}
	}
	return array_keys( $clean );
}

/**
 * The sidebar and the checker, for the post editor only.
 */
function gramoten_enqueue_editor() {
	$screen = get_current_screen();
	if ( ! $screen || 'post' !== $screen->base ) {
		return;
	}
	$url = plugin_dir_url( __FILE__ );

	wp_enqueue_script(
		'gramoten-editor',
		$url . 'build/editor.js',
		array(
			'wp-annotations',
			'wp-api-fetch',
			'wp-blocks',
			'wp-block-editor',
			'wp-components',
			'wp-data',
			'wp-edit-post',
			'wp-editor',
			'wp-element',
			'wp-notices',
			'wp-plugins',
			'wp-rich-text',
		),
		GRAMOTEN_VERSION,
		true
	);
	wp_add_inline_script(
		'gramoten-editor',
		'var gramotenConfig = ' . wp_json_encode(
			array(
				'workerUrl' => add_query_arg( 'ver', GRAMOTEN_VERSION, $url . 'build/worker.js' ),
				'dataUrl'   => $url . 'data/',
				'version'   => GRAMOTEN_VERSION,
				'words'     => array_values( (array) get_user_meta( get_current_user_id(), 'gramoten_words', true ) ),
			)
		) . ';',
		'before'
	);
	wp_enqueue_style( 'gramoten-editor', $url . 'assets/editor.css', array(), GRAMOTEN_VERSION );
}
add_action( 'enqueue_block_editor_assets', 'gramoten_enqueue_editor' );

/**
 * The underlines: this hook also reaches the editor's iframe, where the text is.
 */
function gramoten_enqueue_content() {
	if ( is_admin() ) {
		wp_enqueue_style( 'gramoten-content', plugin_dir_url( __FILE__ ) . 'assets/content.css', array(), GRAMOTEN_VERSION );
	}
}
add_action( 'enqueue_block_assets', 'gramoten_enqueue_content' );
