<?php
/**
 * Plugin Name: Yoast REST Meta (blog-agent)
 * Description: Exposes Yoast focus keyword, meta description and SEO title to the
 *              WordPress REST API so the blog agent can set them when creating posts.
 *
 * Install: save this file as
 *   wp-content/mu-plugins/wp-yoast-rest-meta.php
 * (create the mu-plugins folder if it does not exist). It activates automatically.
 * Do this ONCE per site.
 */

add_action('init', function () {
    $meta = ['_yoast_wpseo_focuskw', '_yoast_wpseo_metadesc', '_yoast_wpseo_title'];
    foreach ($meta as $key) {
        register_post_meta('post', $key, [
            'show_in_rest' => true,
            'single'       => true,
            'type'         => 'string',
            'auth_callback' => function () {
                return current_user_can('edit_posts');
            },
        ]);
    }
});
